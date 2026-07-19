# 用来汇总全部的路由
from fastapi import APIRouter

from app.api.routes.health import router as health_router 
from app.api.routes.trips import router as trips_router 

api_router = APIRouter()
# 把接口装入总路由。
api_router.include_router(health_router)
api_router.include_router(trips_router)

