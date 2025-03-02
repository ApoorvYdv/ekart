from fastapi import APIRouter

from .products import _product_management

product_router = APIRouter()
product_router.include_router(router=_product_management)