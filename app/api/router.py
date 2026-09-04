from fastapi import APIRouter
from app.api.auth import router as auth_router
from app.api.orders import router as orders_router
from app.api.customers import router as customers_router
from app.api.runners import router as runners_router
from app.api.catalog import router as catalog_router
from app.api.ws import router as ws_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth_router)
api_router.include_router(orders_router)
api_router.include_router(customers_router)
api_router.include_router(runners_router)
api_router.include_router(catalog_router)
api_router.include_router(ws_router)
