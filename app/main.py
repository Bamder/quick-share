from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .extensions import engine
from app.models import Base
import app.routes.health as health_router
import app.routes.codes as codes_router
import app.routes.webrtc as webrtc_router
import app.routes.reports as reports_router

# 创建数据库表（如果不存在）
Base.metadata.create_all(bind=engine)

# 创建FastAPI应用
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(health_router.router)
app.include_router(codes_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(webrtc_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(reports_router.router, prefix=settings.API_V1_PREFIX)

@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health"
    }
