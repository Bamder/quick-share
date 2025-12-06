from sqlalchemy import Column, Integer, String, Text, ForeignKey, Enum
from sqlalchemy.orm import relationship
from .base import BaseModel
from .pickup_code import PickupCode

class Report(BaseModel):
    """文件举报表"""
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="举报ID")
    code = Column(
        String(6),
        ForeignKey("pickup_codes.code", ondelete="CASCADE"),
        nullable=False,
        comment="关联取件码"
    )
    reason = Column(Text, nullable=False, comment="举报原因")
    reporter_ip = Column(String(45), comment="举报者IP")
    status = Column(
        Enum("pending", "reviewed", "resolved"),
        default="pending",
        comment="举报处理状态"
    )

    # 关联取件码模型
    pickup_code = relationship("PickupCode", backref="reports")

    def __repr__(self):
        return f"<Report(id={self.id}, code={self.code}, status={self.status})>"