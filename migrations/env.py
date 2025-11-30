from logging.config import fileConfig
import sys
import os
from pathlib import Path
from dotenv import load_dotenv  # 需 pip install python-dotenv

from sqlalchemy import engine_from_config, create_engine  # 新增 create_engine
from sqlalchemy import pool
from alembic import context

# 解决模型导入路径问题（核心：将项目根目录加入Python路径）
sys.path.append(str(Path(__file__).parent.parent))
# 加载 .env 环境变量（优先读环境变量，避免改 alembic.ini）
load_dotenv()

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
from app.models.base import Base
# 导入所有模型，确保 Base 能发现
from app.models.user import User
from app.models.share_session import ShareSession
from app.models.file_info import FileInfo
from app.models.transfer_record import TransferRecord

target_metadata = Base.metadata

# 新增：定义数据库连接URL（统一读取环境变量 DB_URL）
def get_db_url():
    """获取数据库连接URL，优先环境变量，兜底默认值"""
    return os.getenv(
        "DB_URL",  # 匹配你配置的环境变量名（无空格！）
        # 兜底值：和你的数据库信息一致
        "mysql+pymysql://root:123456@localhost:3306/quick_share_dataGrip?charset=utf8mb4"
    )


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    # 直接用自定义函数获取URL，跳过ini文件解析
    url = get_db_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # 忽略 alembic 版本表，避免误操作
        exclude_tables=["alembic_version"],
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # 核心修改：直接用环境变量URL创建引擎，不再读ini的占位符
    db_url = get_db_url()
    # 直接创建连接引擎，跳过config.set_main_option（避免解析ini报错）
    connectable = create_engine(
        db_url,
        poolclass=pool.NullPool  # 保留原有池配置
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # 关键优化：精准对比字段类型/默认值，避免冗余迁移
            compare_type=True,
            compare_server_default=True,
            # 忽略 alembic 版本表
            exclude_tables=["alembic_version"],
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()