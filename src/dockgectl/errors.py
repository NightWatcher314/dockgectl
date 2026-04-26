class DockgectlError(Exception):
    """Base error for dockgectl."""


class ConfigError(DockgectlError):
    pass


class ApiError(DockgectlError):
    pass


class AuthError(DockgectlError):
    pass


class NotFoundError(DockgectlError):
    pass

