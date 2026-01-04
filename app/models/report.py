from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Enum, DateTime, ForeignKey
from .base import Base
from sqlalchemy import Column, Integer, ForeignKey


class Report(Base):
    __tablename__ = 'reports'

    id = Column(Integer, autoincrement=True, primary_key=True, comment='举报ID')
    code = Column(String(6), ForeignKey('pickup_codes.code', ondelete='CASCADE'), nullable=False,
                  comment='关联取件码（6位）')
    reason = Column(Text, nullable=False, comment='举报原因')
    reporter_ip = Column(String(45), comment='举报者IP')
    status = Column(Enum('pending', 'reviewed', 'resolved'), default='pending', comment='举报处理状态')
    created_at = Column(DateTime, comment='创建时间')
    updated_at = Column(DateTime, comment='更新时间')
    user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True, comment='举报者用户ID（可选）')