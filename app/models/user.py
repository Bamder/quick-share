from datetime import datetime
from sqlalchemy import Column, Integer, String, Enum, DateTime
from .base import Base


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, autoincrement=True, primary_key=True, comment='用户ID')
    username = Column(String(50), unique=True, nullable=False, comment='用户名（唯一）')
    password_hash = Column(String(128), nullable=False, comment='密码哈希（不存储明文）')
    email = Column(String(100), unique=True, nullable=True, comment='邮箱（唯一，可选）')
    role = Column(Enum('user', 'admin'), default='user', comment='用户角色（普通用户/管理员）')
    status = Column(Enum('active', 'inactive', 'banned'), default='active', comment='账号状态')
    last_login_ip = Column(String(45), comment='最后登录IP')
    last_login_at = Column(DateTime, comment='最后登录时间')
    created_at = Column(DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = Column(DateTime, onupdate=datetime.utcnow, comment='更新时间')