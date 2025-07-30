import pytest
import requests
from unittest.mock import patch, Mock

from lygos_sdk.client import LygosClient
from lygos_sdk.exceptions import (
    LygosAPIError,
    LygosAuthenticationError,
    LygosInvalidRequestError,
    LygosNetworkError,
    LygosNotFoundError,
    LygosServerError,
    LygosPaymentValidationError,
)

@pytest.fixture
def client():
    """Returns a LygosClient instance with a dummy API key."""
    return LygosClient("test_api_key")

def test_init_requires_api_key():
    """Tests that a ValueError is raised if the API key is empty."""
    with pytest.raises(ValueError, match="API key cannot be empty."):
        LygosClient("")

@patch('requests.post')
def test_create_payment_link_success(mock_post, client):
    """Tests successful creation of a payment link."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"link": "https://pay.lygosapp.com/123"}
    mock_post.return_value = mock_response

    link = client.create_payment_link(
        amount=1000,
        shop_name="Test Shop",
        message="Test payment",
        order_id="test_order_123"
    )

    assert link == "https://pay.lygosapp.com/123"
    mock_post.assert_called_once()
    called_args, called_kwargs = mock_post.call_args
    assert called_kwargs['json']['amount'] == 1000

@patch('requests.post')
def test_create_payment_link_missing_link(mock_post, client):
    """Tests that a LygosAPIError is raised if the 'link' is not in the response."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"message": "Something went wrong"}
    mock_post.return_value = mock_response

    with pytest.raises(LygosAPIError, match="Payment link not found in response."):
        client.create_payment_link(
            amount=1000,
            shop_name="Test Shop",
            message="Test payment",
            order_id="test_order_123"
        )

@patch('requests.post')
def test_create_payment_link_http_errors(mock_post, client):
    """Tests that the correct exception is raised for various HTTP errors."""
    # 400 Bad Request
    mock_response_400 = Mock()
    mock_response_400.status_code = 400
    mock_response_400.json.return_value = {"message": "Bad request"}
    mock_response_400.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response_400)
    mock_post.return_value = mock_response_400
    with pytest.raises(LygosInvalidRequestError):
        client.create_payment_link(1, "", "", "")

    # 401 Unauthorized
    mock_response_401 = Mock()
    mock_response_401.status_code = 401
    mock_response_401.json.return_value = {"message": "Unauthorized"}
    mock_response_401.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response_401)
    mock_post.return_value = mock_response_401
    with pytest.raises(LygosAuthenticationError):
        client.create_payment_link(1, "", "", "")

    # 500 Internal Server Error
    mock_response_500 = Mock()
    mock_response_500.status_code = 500
    mock_response_500.json.return_value = {"message": "Server error"}
    mock_response_500.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response_500)
    mock_post.return_value = mock_response_500
    with pytest.raises(LygosServerError):
        client.create_payment_link(1, "", "", "")

@patch('requests.post')
def test_create_payment_link_network_error(mock_post, client):
    """Tests that LygosNetworkError is raised for network errors."""
    mock_post.side_effect = requests.exceptions.ConnectionError
    with pytest.raises(LygosNetworkError):
        client.create_payment_link(1, "", "", "")

@patch('requests.get')
def test_get_payin_status_success(mock_get, client):
    """Tests successful retrieval of a payin status."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "paid"}
    mock_get.return_value = mock_response

    status = client.get_payin_status("order_123")
    assert status == {"status": "paid"}
    mock_get.assert_called_once_with(
        "https://api.lygosapp.com/v1/gateway/payin/order_123",
        headers=client.headers
    )

@patch('requests.get')
def test_get_payin_status_not_found(mock_get, client):
    """Tests that LygosNotFoundError is raised for a 404 status code."""
    mock_response = Mock()
    mock_response.status_code = 404
    mock_response.json.return_value = {"message": "Not found"}
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response)
    mock_get.return_value = mock_response

    with pytest.raises(LygosNotFoundError):
        client.get_payin_status("unknown_order")


@patch('lygos_sdk.client.LygosClient.get_payin_status')
def test_validate_payment_success(mock_get_status, client):
    """Tests that validate_payment returns data when status is 'paid'."""
    mock_get_status.return_value = {"status": "paid", "order_id": "order_123"}

    result = client.validate_payment("order_123")

    assert result == {"status": "paid", "order_id": "order_123"}
    mock_get_status.assert_called_once_with("order_123")


@patch('lygos_sdk.client.LygosClient.get_payin_status')
def test_validate_payment_failed_status(mock_get_status, client):
    """Tests that validate_payment raises an exception for 'failed' status."""
    mock_get_status.return_value = {"status": "failed", "order_id": "order_123"}

    with pytest.raises(LygosPaymentValidationError, match="Payment validation failed. Status is 'failed'."):
        client.validate_payment("order_123")

    mock_get_status.assert_called_once_with("order_123")


@patch('lygos_sdk.client.LygosClient.get_payin_status')
def test_validate_payment_pending_status(mock_get_status, client):
    """Tests that validate_payment raises an exception for 'pending' status."""
    mock_get_status.return_value = {"status": "pending", "order_id": "order_123"}

    with pytest.raises(LygosPaymentValidationError, match="Payment validation failed. Status is 'pending'."):
        client.validate_payment("order_123")


@patch('lygos_sdk.client.LygosClient.get_payin_status')
def test_validate_payment_missing_status(mock_get_status, client):
    """Tests that validate_payment raises an exception if 'status' key is missing."""
    mock_get_status.return_value = {"order_id": "order_123"}  # No status key

    with pytest.raises(LygosPaymentValidationError, match="Payment validation failed. Status is 'None'."):
        client.validate_payment("order_123")
