from starlette.middleware.base import BaseHTTPMiddleware


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        tenant = request.headers.get("X-Tenant")

        if tenant:
            request.state.tenant = tenant

        response = await call_next(request)
        return response