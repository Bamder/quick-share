# alembic/env.py 完整代码
from logging.config import fileConfig
import sys
from pathlib import Path

from sqlalchemy import engine_from_config, pool
from alembic import context

# -------------------------- 核心配置：添加项目路径 + 导入模型 --------------------------
# 将项目根目录添加到Python路径（确保能导入app模块）
# __file__ = alembic/env.py → 父目录是alembic → 再父目录是项目根目录
sys.path.append(str(Path(__file__).resolve().parent.parent))

# 从模型统一入口导入Base（无需逐个导入模型文件，因为__init__.py已导出所有模型）
from app.models import Base

# -------------------------- 原生Alembic配置（无需修改） --------------------------
# 获取alembic配置对象（读取alembic.ini）
config = context.config

# 配置日志（读取alembic.ini中的日志设置）
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 关键：指定Alembic要识别的模型元数据（必须是Base.metadata）
target_metadata = Base.metadata

# -------------------------- 离线迁移逻辑（无需修改） --------------------------
def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.
    离线模式：仅需数据库URL，无需实际连接数据库
    """
    # 从alembic.ini读取数据库连接地址
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,  # 关联模型元数据
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # 可选：设置编码
        connect_args={"charset": "utf8mb4"}
    )

    with context.begin_transaction():
        context.run_migrations()

# -------------------------- 在线迁移逻辑（无需修改） --------------------------
def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.
    在线模式：需要创建数据库引擎并建立连接
    """
    # 从alembic.ini读取数据库配置，创建引擎
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # 禁用连接池（迁移脚本无需池化）
        # 可选：添加数据库连接参数（如MySQL的charset）
        connect_args={"charset": "utf8mb4"}
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,  # 关联模型元数据
            # 可选：忽略指定表（如需）
            # include_schemas=False,
            # 可选：设置迁移时的比较规则
            # compare_type=True,  # 检测字段类型变化（如int→bigint）
            # compare_server_default=True  # 检测默认值变化
        )

        with context.begin_transaction():
            context.run_migrations()

# -------------------------- 迁移入口（无需修改） --------------------------
if context.is_offline_mode():
    # 离线模式执行
    run_migrations_offline()
else:
    # 在线模式执行
    run_migrations_online()