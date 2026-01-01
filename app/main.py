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
import app.routes.relay as relay_router
import app.routes.reports as reports_router
import logging
import os
import socket

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
    
    # SQLAlchemy 会自动管理连接池


# 创建FastAPI应用
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# 添加验证错误处理器，显示详细错误信息
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    """处理请求验证错误，返回详细的错误信息"""
    # 尝试读取请求体
    body = None
    try:
        # 注意：request.body() 只能读取一次，如果已经读取过会返回空
        # 这里尝试从异常对象中获取
        if hasattr(exc, 'body'):
            body = exc.body
        else:
            # 如果异常对象没有 body，尝试从请求中读取
            body_bytes = await request.body()
            if body_bytes:
                import json
                body = json.loads(body_bytes.decode('utf-8'))
    except Exception as e:
        logger.warning(f"无法读取请求体: {e}")
        pass
    
    error_details = []
    for error in exc.errors():
        field_path = " -> ".join(str(loc) for loc in error.get("loc", []))
        error_details.append({
            "field": field_path,
            "message": error.get("msg", "验证失败"),
            "type": error.get("type", "unknown")
        })
    
    logger.error(f"请求验证失败:")
    logger.error(f"  路径: {request.url.path}")
    logger.error(f"  请求体: {body}")
    logger.error(f"  错误详情: {error_details}")
    
    return JSONResponse(
        status_code=422,
        content={
            "code": 422,
            "msg": "请求数据验证失败",
            "detail": error_details,
            "requestBody": body
        }
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
    # 添加缓存控制：开发环境禁用缓存，生产环境可以启用
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    logger.info(f"静态文件目录已挂载: {static_dir}")
else:
    logger.warning(f"静态文件目录不存在: {static_dir}")

# 注册路由
app.include_router(health_router.router)
app.include_router(codes_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(relay_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(reports_router.router, prefix=settings.API_V1_PREFIX)

@app.get("/")
async def root():
    """根路径，返回前端欢迎页"""
    return await welcome_page()

@app.get("/welcome")
async def welcome_page():
    """欢迎页面路由"""
    welcome_path = os.path.join(static_dir, "pages", "welcome", "welcome.html")
    if os.path.exists(welcome_path):
        return FileResponse(
            welcome_path,
            media_type="text/html",
            headers={"Cache-Control": "no-cache"}
        )
    else:
        logger.warning(f"欢迎页文件未找到: {welcome_path}")
        return {
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "docs": "/docs",
            "health": "/health",
            "error": f"欢迎页文件未找到: {welcome_path}"
        }

@app.get("/index")
async def index_page():
    """主页面路由（文件传输页面）"""
    index_path = os.path.join(static_dir, "pages", "index", "index.html")
    if os.path.exists(index_path):
        return FileResponse(
            index_path,
            media_type="text/html",
            headers={"Cache-Control": "no-cache"}
        )
    else:
        logger.warning(f"主页面文件未找到: {index_path}")
        return {
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "docs": "/docs",
            "health": "/health",
            "error": f"主页面文件未找到: {index_path}"
        }
