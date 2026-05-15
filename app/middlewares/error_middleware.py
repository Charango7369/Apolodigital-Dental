from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        try:
            return await call_next(request)
        except Exception as ex:
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "message": str(ex),
                    "data": None,
                },
            )