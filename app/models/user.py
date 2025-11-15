# models/user.py
from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from .base import Base  # 从 base.py 导入基类


# 定义用户表模型，继承 Base
class User(Base):
    __tablename__ = "user"  # 数据库表名（必须小写，避免SQL关键字冲突）

    # 字段定义
    id = Column(Integer, primary_key=True, autoincrement=True)  # 主键，自增
    username = Column(String(50), unique=True, nullable=False)  # 用户名（唯一，不能为空）
    email = Column(String(100), unique=True, nullable=False)  # 邮箱（唯一，不能为空）
    created_at = Column(DateTime, default=datetime.now)  # 创建时间（默认当前时间）