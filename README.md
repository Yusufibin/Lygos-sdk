# Lygos Python SDK

A Python SDK for interacting with the Lygos API.

## Installation

You can install the SDK using pip (once it's published):

```bash
pip install lygos-sdk
```

For now, you can install it directly from the source code:
```bash
pip install .
```
Or, for development, in editable mode:
```bash
pip install -e .
```

## Usage

First, you need to initialize the `LygosClient` with your API key.

```python
from lygos_sdk.client import LygosClient
from lygos_sdk.exceptions import LygosAPIError, LygosNetworkError, LygosNotFoundError

# It's recommended to load the API key from environment variables
# or a secure configuration management system.
api_key = "your_lygos_api_key"
client = LygosClient(api_key=api_key)
```

### Create a Payment Link

You can create a payment link by calling the `create_payment_link` method.

```python
try:
    payment_link = client.create_payment_link(
        amount=2500, # Amount in the smallest currency unit
        shop_name="My Awesome Shop",
        message="Payment for Order #XYZ-123",
        order_id="unique_order_id_xyz_123",
        success_url="https://example.com/payment/success",
        failure_url="https://example.com/payment/failure"
    )
    print(f"Payment link successfully created: {payment_link}")
    # Redirect your user to this link to complete the payment
except LygosAPIError as e:
    print(f"An API error occurred: {e} (Status: {e.status_code})")
except LygosNetworkError as e:
    print(f"A network error occurred: {e}")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
```

### Verifying Payments (Recommended)

After the user is redirected back to your application from the Lygos payment page, you **must** verify the status of the transaction to confirm if the payment was successful. A user landing on your `success_url` is not a guarantee of a successful payment.

The `validate_payment` method simplifies this process. It checks the status and raises an exception if the payment was not successful, making your success handler clean and secure.

```python
# In your success handler (e.g., a Flask route)
from lygos_sdk.exceptions import LygosPaymentValidationError, LygosNotFoundError

order_id = "unique_order_id_xyz_123" # The order_id from your success_url

try:
    payment_details = client.validate_payment(order_id=order_id)
    print(f"Payment for order {payment_details['order_id']} was successful!")
    # Safely activate the user's subscription, ship the product, etc.

except LygosPaymentValidationError as e:
    # This exception is raised if the status is 'pending', 'failed', etc.
    print(f"Payment not complete: {e}")
    # Advise the user that the payment is not yet confirmed.
    # You can inspect e.response_body for more details.

except LygosNotFoundError:
    print("The requested order was not found. Invalid order_id.")
    # Handle invalid order

except LygosAPIError as e:
    print(f"An API error occurred: {e}")
    # Handle other generic API errors
```

### Retrieving Transaction Status

If you need to check the status of a transaction without raising an exception for non-paid statuses, you can use the `get_payin_status` method.

```python
try:
    status = client.get_payin_status(order_id="unique_order_id_xyz_123")
    print(f"Transaction status: {status}")
except LygosNotFoundError:
    print("The requested order was not found.")
except LygosAPIError as e:
    print(f"An API error occurred: {e} (Status: {e.status_code})")
except LygosNetworkError as e:
    print(f"A network error occurred: {e}")
```

## Error Handling

The SDK uses custom exceptions to make error handling more specific and intuitive. All exceptions inherit from `LygosError`.

- `LygosAPIError`: The base exception for errors returned by the Lygos API.
- `LygosAuthenticationError`: Raised for authentication issues (e.g., an invalid API key).
- `LygosInvalidRequestError`: Raised for invalid request parameters (e.g., a missing field).
- `LygosNotFoundError`: Raised when a requested resource (like an order) is not found.
- `LygosServerError`: Raised for errors on the Lygos server side.
- `LygosNetworkError`: Raised for network-related issues, such as a connection timeout.

## Development

To contribute to this project, please follow these steps.

### Running Tests

First, install the development dependencies:

```bash
# Install pytest and other testing requirements
pip install pytest requests

# Install the SDK in editable mode
pip install -e .
```

Then, run the test suite using `pytest` from the root directory:

```bash
pytest
```
