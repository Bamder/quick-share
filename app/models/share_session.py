# share_session.py

from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base

class ShareSession(Base):
    """分享会话表模型"""
    __tablename__ = 'share_session'

    # 字段定义
    session_id = Column(String(50), primary_key=True, comment='传输会话唯一ID（UUID）')
    sharer_id = Column(String(50), ForeignKey('user.user_id', ondelete='CASCADE'), nullable=False, comment='分享者ID（关联用户表）')
    max_share_count = Column(Integer, nullable=False, comment='最大分享人数')
    time_limit = Column(Integer, nullable=False, comment='分享时间限制（分钟，0表示无限制）')
    access_password = Column(String(50), nullable=False, comment='分享码（加密存储）')
    sharer_sdp_offer = Column(String(255), nullable=True, comment='分享者SDP Offer')
    sharer_ip = Column(String(50), nullable=True, comment='分享者IP地址')
    sharer_port = Column(Integer, nullable=True, comment='分享者端口号')
    create_time = Column(DateTime, nullable=False, comment='会话创建时间')
    expire_time = Column(DateTime, nullable=True, comment='会话过期时间')
    status = Column(Boolean, nullable=False, comment='会话状态（1-有效，0-已过期/关闭）')

    # 关系定义
    # 一个分享会话属于一个分享者（User）
    sharer = relationship("User", backref="sessions")
    # 一个分享会话包含多个文件信息（FileInfo）
    files = relationship("FileInfo", backref="session", cascade="all, delete-orphan")
    # 一个分享会话包含多个传输记录（TransferRecord）
    transfer_records = relationship("TransferRecord", backref="session", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ShareSession(session_id='{self.session_id}', sharer_id='{self.sharer_id}', status='{self.status}')>"