from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from .config import settings
from .extensions import engine
from contextlib import asynccontextmanager
from app.models import Base
import app.routes.health as health_router
import app.routes.codes as codes_router
import app.routes.webrtc as webrtc_router
import app.routes.reports as reports_router
import logging
import os

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理
    - 启动时：创建数据库表（如果不存在）
    - 关闭时：清理资源
    
    注意：数据库环境检查已在启动脚本中完成，这里假设环境已就绪
    """
    # 启动时：创建数据库表
    # 注意：数据库环境检查已在启动脚本中完成，这里应该能成功
    try:
        logger.info("正在检查并创建数据库表（如果不存在）...")
        Base.metadata.create_all(bind=engine)
        logger.info("数据库表检查完成，所有表已就绪")
    except Exception as e:
        # 如果这里还失败，可能是：
        # 1. 启动脚本的检查有遗漏
        # 2. 数据库环境在启动后发生了变化
        # 3. 数据库权限不足
        error_msg = str(e)
        logger.error("=" * 60)
        logger.error("数据库连接失败，无法创建表")
        logger.error("=" * 60)
        logger.error(f"错误详情: {error_msg}")
        logger.error("")
        logger.error("可能的原因：")
        logger.error("  1. 数据库服务在启动后停止")
        logger.error("  2. 数据库连接配置发生变化")
        logger.error("  3. 数据库用户权限不足（无法创建表）")
        logger.error("  4. 数据库连接数达到上限")
        logger.error("")
        logger.error("建议操作：")
        logger.error("  1. 检查 MySQL 服务是否仍在运行")
        logger.error("  2. 重新运行启动脚本进行环境检查")
        logger.error("  3. 检查数据库用户权限")
        logger.error("=" * 60)
        # 抛出异常，阻止应用启动（应用需要数据库才能正常工作）
        raise RuntimeError(
            f"数据库初始化失败: {error_msg}\n"
            "请检查数据库服务状态和连接配置，然后重新启动应用。"
        ) from e
    
    yield
    
    # 关闭时：目前无需特殊清理，SQLAlchemy 会自动管理连接池


# 创建FastAPI应用
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 配置静态文件服务
# 获取项目根目录
# __file__ 是 app/main.py，所以需要向上两级到项目根目录
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
static_dir = os.path.join(project_root, "static")

# 挂载静态文件目录
if os.path.exists(static_dir):
    # 挂载静态资源（CSS、JS、图片等）
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    logger.info(f"静态文件目录已挂载: {static_dir}")
else:
    logger.warning(f"静态文件目录不存在: {static_dir}")

# 注册路由
app.include_router(health_router.router)
app.include_router(codes_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(webrtc_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(reports_router.router, prefix=settings.API_V1_PREFIX)

@app.get("/")
async def root():
    """返回前端欢迎页"""
    welcome_path = os.path.join(static_dir, "pages", "welcome.html")
    if os.path.exists(welcome_path):
        return FileResponse(
            welcome_path,
            media_type="text/html",
            headers={"Cache-Control": "no-cache"}
        )
    else:
        # 如果找不到欢迎页，尝试返回首页
        index_path = os.path.join(static_dir, "pages", "index.html")
        if os.path.exists(index_path):
            return FileResponse(
                index_path,
                media_type="text/html",
                headers={"Cache-Control": "no-cache"}
            )
        else:
            # 如果都找不到，返回 API 信息
            logger.warning(f"前端文件未找到: {welcome_path} 和 {index_path}")
            logger.warning(f"项目根目录: {project_root}")
            logger.warning(f"静态文件目录: {static_dir}")
            return {
                "app": settings.APP_NAME,
                "version": settings.APP_VERSION,
                "docs": "/docs",
                "health": "/health",
                "note": f"前端文件未找到: {welcome_path}",
                "debug": {
                    "project_root": project_root,
                    "static_dir": static_dir,
                    "welcome_path": welcome_path,
                    "index_path": index_path
                }
            }
