from starlette.middleware.base import BaseHTTPMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi import HTTPException as FastAPIHTTPException
from fastapi.responses import JSONResponse


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        try:
            return await call_next(request)
        except (FastAPIHTTPException, StarletteHTTPException) as http_ex:
            headers = getattr(http_ex, "headers", None)
            return JSONResponse(
                status_code=http_ex.status_code,
                content={"detail": http_ex.detail},
                headers=headers,
            )
        except Exception as ex:
            return JSONResponse(
                status_code=500,
                content={
                    "detail": str(ex),
                    "success": False,
                    "message": str(ex),
                    "data": None,
                },
            )
