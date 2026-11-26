class ServiceError(Exception):
    """A business rule refused the move. Routes turn it into an HTTP error with the same code."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.http_status = status
        self.code = code
        self.message = message
