# app/deps.py
from fastapi import Query


def pagination_params(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    """Dependência simples de paginação."""
    skip = (page - 1) * page_size
    limit = page_size
    return {"page": page, "page_size": page_size, "skip": skip, "limit": limit}
