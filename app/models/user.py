# user.py

from sqlalchemy import Column, String, Integer, DateTime, Boolean
from .base import Base

class User(Base):
    """用户表模型"""
    __tablename__ = 'user'  # 对应数据库中的表名

    # 字段定义
    user_id = Column(String(50), primary_key=True, comment='用户唯一标识（UUID）')
    username = Column(String(50), nullable=True, comment='用户名（非必填）')
    login_account = Column(String(100), unique=True, nullable=True, comment='登录账号（唯一）')
    password_hash = Column(String(255), nullable=True, comment='登录密码哈希值')

    # __repr__ 方法用于在打印对象时提供更友好的输出
    def __repr__(self):
        return f"<User(user_id='{self.user_id}', username='{self.username}', login_account='{self.login_account}')>"