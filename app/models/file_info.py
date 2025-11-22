# file_info.py

from sqlalchemy import Column, String, Integer, ForeignKey, BigInteger
from sqlalchemy.orm import relationship
from .base import Base

class FileInfo(Base):
    """文件信息表模型"""
    __tablename__ = 'file_info'

    # 字段定义
    file_id = Column(String(50), primary_key=True, comment='文件唯一标识（UUID）')
    session_id = Column(String(50), ForeignKey('share_session.session_id', ondelete='CASCADE'), nullable=False, comment='关联会话ID')
    file_name = Column(String(255), nullable=False, comment='文件原始名称')
    file_size = Column(BigInteger, nullable=False, comment='文件大小（字节）')
    file_type = Column(String(50), nullable=True, comment='文件类型')
    file_hash = Column(String(100), nullable=True, comment='文件哈希值（校验完整性）')

    # 关系定义
    # 一个文件信息属于一个分享会话（ShareSession）
    session = relationship("ShareSession")

    def __repr__(self):
        return f"<FileInfo(file_id='{self.file_id}', file_name='{self.file_name}', session_id='{self.session_id}')>"