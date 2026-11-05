from fastapi import HTTPException, status


class NotFoundException(HTTPException):
    """Base exception for resource not found errors."""

    def __init__(self, detail: str = "Resource not found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class BadRequestException(HTTPException):
    """The request is well-formed but asks for something that cannot be done."""

    def __init__(self, detail: str = "Bad request"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class AlreadyExistsException(HTTPException):
    """Base exception for resource already exists errors."""

    def __init__(self, detail: str = "Resource already exists"):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class UnauthorizedException(HTTPException):
    """Base exception for unauthorized access errors."""

    def __init__(self, detail: str = "Unauthorized access"):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


class ForbiddenException(HTTPException):
    """Base exception for forbidden access errors."""

    def __init__(self, detail: str = "Access forbidden"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class RateLimitedException(HTTPException):
    """Too many requests. `Retry-After` is for a client, `detail` for a person."""

    def __init__(self, retry_after: int):
        if retry_after < 60:
            wait = f"{retry_after} second{'' if retry_after == 1 else 's'}"
        else:
            minutes = -(-retry_after // 60)
            wait = f"{minutes} minute{'' if minutes == 1 else 's'}"
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many attempts. Try again in {wait}",
            headers={"Retry-After": str(retry_after)},
        )


class ServiceUnavailableException(HTTPException):
    """A dependency this endpoint needs is not configured or not reachable."""

    def __init__(self, detail: str = "Service unavailable"):
        super().__init__(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)


class PayloadTooLargeException(HTTPException):
    """An upload over the size limit. The message names the limit."""

    def __init__(self, detail: str = "That file is too large"):
        super().__init__(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=detail
        )


class UnsupportedMediaTypeException(HTTPException):
    """An upload whose bytes are not an image we accept, whatever it claims."""

    def __init__(self, detail: str = "That file type is not supported"):
        super().__init__(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=detail
        )
