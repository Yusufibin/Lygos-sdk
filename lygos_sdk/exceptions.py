class LygosError(Exception):
    """Base exception class for Lygos SDK errors."""
    pass

class LygosAPIError(LygosError):
    """Raised for errors returned by the Lygos API."""
    def __init__(self, message, status_code=None, response_body=None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body

    def __str__(self):
        if self.status_code:
            return f"({self.status_code}) {super().__str__()}"
        return super().__str__()

class LygosAuthenticationError(LygosAPIError):
    """Raised for authentication errors (e.g., invalid API key)."""
    pass

class LygosInvalidRequestError(LygosAPIError):
    """Raised for invalid requests (e.g., missing parameters)."""
    pass

class LygosNotFoundError(LygosAPIError):
    """Raised when a resource is not found."""
    pass

class LygosServerError(LygosAPIError):
    """Raised for errors on the Lygos server side."""
    pass

class LygosNetworkError(LygosError):
    """Raised for network-related errors (e.g., connection issues)."""
    pass


class LygosPaymentValidationError(LygosAPIError):
    """Raised when a payment validation fails (e.g., status is not 'paid')."""
    pass
