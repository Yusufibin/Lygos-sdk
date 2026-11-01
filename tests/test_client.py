from unittest.mock import Mock, patch

import pytest
import requests

from lygos_sdk import LygosClient, LygosError
from lygos_sdk.exceptions import (
    LygosAPIError,
    LygosAuthenticationError,
    LygosInvalidRequestError,
    LygosNetworkError,
    LygosNotFoundError,
    LygosPaymentValidationError,
    LygosRateLimitError,
    LygosServerError,
)


@pytest.fixture
def transport():
    session = Mock(spec=requests.Session)
    response = Mock(spec=requests.Response)
    response.status_code = 200
    response.json.return_value = {"link": "https://pay.lygosapp.com/example"}
    session.request.return_value = response
    return session


@pytest.fixture
def client(transport):
    return LygosClient("unit-test-key", session=transport)


def create(client, **overrides):
    args = dict(amount=2500, shop_name="Test shop", message="Test", order_id="order-1")
    return client.create_payment_link(**(args | overrides))


def test_payment_payload_timeouts_and_redirect_policy(client, transport):
    assert create(client, meta_data={}) == "https://pay.lygosapp.com/example"
    transport.request.assert_called_once_with(
        "POST",
        client.BASE_API_URL + "/gateway",
        headers=client.headers,
        timeout=(5.0, 30.0),
        allow_redirects=False,
        json={
            "amount": 2500,
            "shop_name": "Test shop",
            "message": "Test",
            "order_id": "order-1",
            "meta_data": {},
        },
    )
    transport.request.return_value.close.assert_called_once()


def test_status_encodes_order_as_one_path_segment(client, transport):
    transport.request.return_value.json.return_value = {"status": "paid"}
    assert client.get_payin_status("order/one ?") == {"status": "paid"}
    assert transport.request.call_args.args[1].endswith("/order%2Fone%20%3F")


@pytest.mark.parametrize(
    "status,error",
    [
        (400, LygosInvalidRequestError),
        (401, LygosAuthenticationError),
        (403, LygosAuthenticationError),
        (404, LygosNotFoundError),
        (422, LygosInvalidRequestError),
        (429, LygosRateLimitError),
        (500, LygosServerError),
        (302, LygosAPIError),
    ],
)
def test_http_errors_use_typed_exceptions_and_close_response(client, transport, status, error):
    response = transport.request.return_value
    response.status_code = status
    response.json.return_value = {"detail": {"message": "Provider response"}}
    with pytest.raises(error) as caught:
        create(client)
    assert caught.value.status_code == status
    assert "Provider response" in str(caught.value)
    response.close.assert_called_once()


@pytest.mark.parametrize("value", [[], None, "not-an-object", 100])
def test_malformed_success_json_is_a_sdk_error(client, transport, value):
    transport.request.return_value.json.return_value = value
    with pytest.raises(LygosAPIError, match="instead of an object"):
        client.get_payin_status("order")


def test_invalid_json_on_success_and_non_json_errors(client, transport):
    response = transport.request.return_value
    response.json.side_effect = ValueError("bad json")
    with pytest.raises(LygosAPIError, match="invalid JSON"):
        create(client)
    response.status_code = 503
    with pytest.raises(LygosServerError, match="HTTP 503"):
        create(client)


def test_timeout_never_retries_or_exposes_credentials(client, transport):
    transport.request.side_effect = requests.Timeout("unit-test-key")
    with pytest.raises(LygosNetworkError) as caught:
        create(client)
    assert "unit-test-key" not in str(caught.value)
    assert caught.value.__suppress_context__
    transport.request.assert_called_once()


def test_reflected_api_keys_are_redacted_from_errors(client, transport):
    response = transport.request.return_value
    response.status_code = 401
    response.json.return_value = {"message": "invalid unit-test-key", "nested": ["unit-test-key"]}
    with pytest.raises(LygosAuthenticationError) as caught:
        create(client)
    assert "unit-test-key" not in str(caught.value)
    assert "unit-test-key" not in str(caught.value.response_body)


@pytest.mark.parametrize("amount", [0, -1, True, 1.2, "2500"])
def test_amounts_are_not_silently_coerced(client, transport, amount):
    with pytest.raises(ValueError, match="positive integer"):
        create(client, amount=amount)
    transport.request.assert_not_called()


@pytest.mark.parametrize("key", ["", " ", None, "x\r\ny"])
def test_api_key_validation(key):
    with pytest.raises(ValueError):
        LygosClient(key)


@pytest.mark.parametrize("timeout", [0, -1, False, float("inf"), (1, 0), (1,), None])
def test_timeout_validation(timeout):
    with pytest.raises(ValueError):
        LygosClient("test", timeout=timeout)


def test_custom_timeout_and_base_url(transport):
    client = LygosClient("test", timeout=12, base_url="https://example.test/v1/", session=transport)
    client.get_payin_status("id")
    assert transport.request.call_args.kwargs["timeout"] == 12
    assert transport.request.call_args.args[1] == "https://example.test/v1/gateway/payin/id"
    with pytest.raises(ValueError):
        LygosClient("test", base_url="http://example.test")


@pytest.mark.parametrize(
    "payload",
    [{"status": "pending"}, {"status": "failed"}, {}, {"status": "paid", "order_id": "different"}],
)
def test_payment_validation_rejects_unconfirmed_or_mismatched_orders(client, transport, payload):
    transport.request.return_value.json.return_value = payload
    with pytest.raises(LygosPaymentValidationError):
        client.validate_payment("order-1")


def test_payment_validation_accepts_paid_same_order(client, transport):
    payload = {"status": "paid", "order_id": "order-1"}
    transport.request.return_value.json.return_value = payload
    assert client.validate_payment("order-1") == payload


@pytest.mark.parametrize(
    "link", [None, 0, "javascript:alert(1)", "https://user:password@example.test"]
)
def test_invalid_payment_links_are_rejected(client, transport, link):
    transport.request.return_value.json.return_value = {"link": link}
    with pytest.raises(LygosAPIError):
        create(client)


def test_client_lifecycle_preserves_external_session(transport):
    with LygosClient("test", session=transport) as client:
        client.get_payin_status("order")
    transport.close.assert_not_called()
    with pytest.raises(LygosError, match="closed"):
        client.get_payin_status("order")
    with patch("requests.Session", return_value=transport):
        with LygosClient("test"):
            pass
    transport.close.assert_called_once()
