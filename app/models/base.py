from datetime import datetime
from sqlalchemy import Column, DateTime
from sqlalchemy.ext.declarative import declarative_base

# 定义基类，所有模型继承此类
Base = declarative_base()

class BaseModel(Base):
    """通用模型基类，提取公共字段"""
    __abstract__ = True  # 标记为抽象类，不生成实际表

    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="更新时间"
    )