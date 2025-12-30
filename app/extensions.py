from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings

# 使用配置中的数据库URL（从环境变量读取）
DATABASE_URL = settings.DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=False,  # 禁用预连接，避免导入时就连接数据库
    pool_recycle=3600,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
