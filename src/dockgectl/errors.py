class DockgectlError(Exception):
    """Base error for dockgectl."""


class ConfigError(DockgectlError):
    pass


class ApiError(DockgectlError):
    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        endpoint: str | None = None,
        retryable: bool = False,
    ):
        super().__init__(message)
        self.code = code
        self.endpoint = endpoint
        self.retryable = retryable


class AuthError(DockgectlError):
    pass


class NotFoundError(DockgectlError):
    pass
