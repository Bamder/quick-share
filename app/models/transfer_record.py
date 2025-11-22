# transfer_record.py

from sqlalchemy import Column, String, Integer, ForeignKey, BigInteger, Boolean, Text
from sqlalchemy.orm import relationship
from .base import Base

class TransferRecord(Base):
    """传输记录表模型"""
    __tablename__ = 'transfer_record'

    # 字段定义
    record_id = Column(String(50), primary_key=True, comment='传输记录唯一标识（UUID）')
    session_id = Column(String(50), ForeignKey('share_session.session_id', ondelete='CASCADE'), nullable=False, comment='关联会话ID')
    sharer_id = Column(String(50), ForeignKey('user.user_id', ondelete='CASCADE'), nullable=False, comment='分享者ID')
    receiver_id = Column(String(50), ForeignKey('user.user_id', ondelete='CASCADE'), nullable=False, comment='接收者ID')
    receiver_sdp_answer = Column(Text, nullable=True, comment='接收者SDP Answer')
    receiver_ip = Column(String(50), nullable=True, comment='接收者IP地址')
    receiver_port = Column(Integer, nullable=True, comment='接收者端口号')
    is_completed = Column(Boolean, nullable=False, comment='是否传输完成（1-完成，0-未完成）')
    transfer_size = Column(BigInteger, default=0, comment='已传输字节数')

    # 关系定义
    # 一个传输记录关联一个分享会话
    session = relationship("ShareSession")
    # 一个传输记录关联一个分享者
    sharer = relationship("User", foreign_keys=[sharer_id])
    # 一个传输记录关联一个接收者
    receiver = relationship("User", foreign_keys=[receiver_id])

    def __repr__(self):
        return f"<TransferRecord(record_id='{self.record_id}', session_id='{self.session_id}', is_completed='{self.is_completed}')>"