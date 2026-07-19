from fastapi import FastAPI

from app.api.router import api_router
#创建了整个 TravelMind 的 FastAPI 应用对象。它保存了：
# 应用名称
# 应用版本
# 注册了哪些接口
# OpenAPI 文档信息
# 中间件
# 启动和关闭逻辑
# 异常处理规则
app = FastAPI(title="TravelMind", version="0.1.0")
# 把总路由注册到 FastAPI 应用。
app.include_router(api_router)

