from fastapi import Query


def pagination_params(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
):
    return {
        "offset": (page - 1) * limit,
        "limit": limit,
    }