"""Synchronous Lygos client with bounded requests and explicit error handling."""

import math
from typing import Dict, Optional
from urllib.parse import quote, urlparse

import requests

from .exceptions import (
    LygosAPIError,
    LygosAuthenticationError,
    LygosError,
    LygosInvalidRequestError,
    LygosNetworkError,
    LygosNotFoundError,
    LygosPaymentValidationError,
    LygosRateLimitError,
    LygosServerError,
)


class LygosClient:
    BASE_API_URL = "https://api.lygosapp.com/v1"

    def __init__(
        self,
        api_key: str,
        *,
        timeout=(5.0, 30.0),
        base_url: str = BASE_API_URL,
        session: Optional[requests.Session] = None,
    ):
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("API key cannot be empty.")
        if any(c in api_key for c in "\r\n"):
            raise ValueError("API key must not contain newlines.")
        values = timeout if isinstance(timeout, tuple) else (timeout,)
        if len(values) not in (1, 2) or any(
            isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0
            for v in values
        ):
            raise ValueError("timeout must be positive seconds or a (connect, read) pair.")
        if isinstance(timeout, tuple) and len(timeout) != 2:
            raise ValueError("timeout tuple must contain connect and read seconds.")
        parsed = urlparse(base_url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "base_url must be an HTTPS API URL without credentials, query or fragment."
            )
        self.api_key = api_key
        self.timeout = timeout
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        self._session = session if session is not None else requests.Session()
        self._owns_session = session is None
        self._closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        if not self._closed and self._owns_session:
            self._session.close()
        self._closed = True

    def _redact(self, value):
        if isinstance(value, str):
            return value.replace(self.api_key, "[redacted]")
        if isinstance(value, dict):
            return {self._redact(k): self._redact(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._redact(v) for v in value]
        return value

    def _handle_api_error(self, response):
        try:
            body = self._redact(response.json())
        except ValueError:
            body = None
        message = None
        if isinstance(body, dict):
            message = body.get("message")
            detail = body.get("detail")
            if not isinstance(message, str) and isinstance(detail, dict):
                message = detail.get("message")
            elif not isinstance(message, str) and isinstance(detail, str):
                message = detail
        if not isinstance(message, str) or not message:
            message = f"Lygos returned HTTP {response.status_code}."
        status = response.status_code
        error = {
            400: LygosInvalidRequestError,
            401: LygosAuthenticationError,
            403: LygosAuthenticationError,
            404: LygosNotFoundError,
            422: LygosInvalidRequestError,
            429: LygosRateLimitError,
        }.get(status, LygosServerError if status >= 500 else LygosAPIError)
        raise error(message[:1000], status, body)

    def _request(self, method: str, path: str, **kwargs) -> Dict:
        if self._closed:
            raise LygosError("This client is closed. Create a new LygosClient.")
        try:
            response = self._session.request(
                method,
                self.base_url + path,
                headers=self.headers,
                timeout=self.timeout,
                allow_redirects=False,
                **kwargs,
            )
        except requests.RequestException:
            # A timed-out POST may already have been accepted. Never retry it implicitly.
            raise LygosNetworkError(
                "Lygos request failed or timed out. Check the order status before retrying a payment request."
            ) from None
        try:
            if not 200 <= response.status_code < 300:
                self._handle_api_error(response)
            try:
                body = response.json()
            except ValueError:
                raise LygosAPIError("Lygos returned invalid JSON.", response.status_code) from None
            if not isinstance(body, dict):
                raise LygosAPIError(
                    "Lygos returned a JSON value instead of an object.", response.status_code
                )
            return body
        finally:
            response.close()

    @staticmethod
    def _order_id(value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("order_id must be a non-empty string.")
        return value

    def create_payment_link(
        self,
        amount: int,
        shop_name: str,
        message: str,
        order_id: str,
        meta_data: Optional[Dict] = None,
        success_url: Optional[str] = None,
        failure_url: Optional[str] = None,
    ) -> str:
        """Create a gateway once. Amount is sent as an integer without currency conversion."""
        if type(amount) is not int or amount <= 0:
            raise ValueError("amount must be a positive integer.")
        if not isinstance(shop_name, str) or not shop_name.strip():
            raise ValueError("shop_name must be a non-empty string.")
        payload = {
            "amount": amount,
            "shop_name": shop_name,
            "message": message,
            "order_id": self._order_id(order_id),
        }
        for name, value in (
            ("meta_data", meta_data),
            ("success_url", success_url),
            ("failure_url", failure_url),
        ):
            if value is not None:
                payload[name] = value
        data = self._request("POST", "/gateway", json=payload)
        link = data.get("link")
        if not isinstance(link, str) or not link:
            raise LygosAPIError("Payment link not found in response.")
        parsed = urlparse(link)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or any(c in link for c in "\r\n")
        ):
            raise LygosAPIError("Lygos returned an invalid payment link.")
        return link

    def get_payin_status(self, order_id: str) -> Dict:
        return self._request("GET", "/gateway/payin/" + quote(self._order_id(order_id), safe=""))

    def validate_payment(self, order_id: str) -> Dict:
        """Accept only the existing 'paid' status convention; this is not reconciliation."""
        data = self.get_payin_status(order_id)
        returned_order = data.get("order_id")
        if returned_order and returned_order != order_id:
            raise LygosPaymentValidationError(
                "Payment order does not match the requested order.", 200, self._redact(data)
            )
        if data.get("status") == "paid":
            return data
        raise LygosPaymentValidationError(
            f"Payment validation failed. Status is '{self._redact(data.get('status'))}'.",
            200,
            self._redact(data),
        )
