import requests
from typing import Optional, Dict

from .exceptions import (
    LygosAPIError,
    LygosAuthenticationError,
    LygosInvalidRequestError,
    LygosNetworkError,
    LygosNotFoundError,
    LygosServerError,
)

class LygosClient:
    """
    A client for interacting with the Lygos API.
    """
    BASE_API_URL = "https://api.lygosapp.com/v1"

    def __init__(self, api_key: str):
        """
        Initializes the LygosClient.

        :param api_key: Your Lygos API key.
        """
        if not api_key:
            raise ValueError("API key cannot be empty.")

        self.api_key = api_key
        self.headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json",
        }

    def _handle_api_error(self, response: requests.Response):
        """Helper function to handle API errors."""
        try:
            error_data = response.json()
            message = error_data.get("message", "An unknown API error occurred.")
        except requests.exceptions.JSONDecodeError:
            message = response.text
            error_data = None

        status_code = response.status_code
        if status_code == 400:
            raise LygosInvalidRequestError(message, status_code, error_data)
        if status_code == 401:
            raise LygosAuthenticationError(message, status_code, error_data)
        if status_code == 404:
            raise LygosNotFoundError(message, status_code, error_data)
        if status_code >= 500:
            raise LygosServerError(message, status_code, error_data)

        raise LygosAPIError(message, status_code, error_data)

    def create_payment_link(
        self,
        amount: int,
        shop_name: str,
        message: str,
        order_id: str,
        meta_data: Optional[Dict] = None,
        success_url: Optional[str] = None,
        failure_url: Optional[str] = None
    ) -> str:
        """
        Creates a payment gateway link.

        :param amount: The amount to be paid.
        :param shop_name: The name of the shop.
        :param message: A message to be displayed to the user.
        :param order_id: A unique identifier for the order.
        :param meta_data: Optional metadata for the transaction.
        :param success_url: The URL to redirect to on successful payment.
        :param failure_url: The URL to redirect to on failed payment.
        :return: The payment link URL.
        """
        create_gateway_url = f"{self.BASE_API_URL}/gateway"
        payload = {
            "amount": int(amount),
            "shop_name": shop_name,
            "message": message,
            "order_id": order_id,
        }
        if meta_data:
            payload["meta_data"] = meta_data
        if success_url:
            payload["success_url"] = success_url
        if failure_url:
            payload["failure_url"] = failure_url

        try:
            response = requests.post(create_gateway_url, headers=self.headers, json=payload)
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            self._handle_api_error(e.response)
        except requests.exceptions.RequestException as e:
            raise LygosNetworkError(f"Network error while creating payment link: {e}") from e

        response_data = response.json()
        payment_link = response_data.get("link")

        if not payment_link:
            raise LygosAPIError("Payment link not found in response.")

        return payment_link

    def get_payin_status(self, order_id: str) -> Dict:
        """
        Retrieves the status of a specific payin transaction.

        :param order_id: The order ID of the transaction to check.
        :return: A dictionary containing the transaction status.
        """
        get_payin_status_url = f"{self.BASE_API_URL}/gateway/payin/{order_id}"

        try:
            response = requests.get(get_payin_status_url, headers=self.headers)
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            self._handle_api_error(e.response)
        except requests.exceptions.RequestException as e:
            raise LygosNetworkError(f"Network error while getting payin status: {e}") from e

        return response.json()
