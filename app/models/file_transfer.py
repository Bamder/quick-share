from sqlalchemy import Column, Integer, String, ForeignKey, Enum, Float, DateTime
from sqlalchemy.orm import relationship
from .base import BaseModel
from .pickup_code import PickupCode

class FileTransfer(BaseModel):
    """文件中转传输状态表（服务器→接收者）"""
    __tablename__ = "file_transfers"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="传输记录ID")
    code = Column(
        String(6),
        ForeignKey("pickup_codes.code", ondelete="CASCADE"),
        nullable=False,
        comment="关联取件码"
    )
    receiver_ip = Column(String(45), comment="接收者IP")
    status = Column(
        Enum("pending", "transferring", "completed", "failed"),
        default="pending",
        comment="传输状态：等待中/传输中/完成/失败"
    )
    progress = Column(Float, default=0.0, comment="传输进度（0.0-100.0）")
    completed_at = Column(DateTime, comment="传输完成时间")

    # 关联取件码
    pickup_code = relationship("PickupCode", backref="file_transfers")

    def __repr__(self):
        return f"<FileTransfer(code={self.code}, status={self.status}, progress={self.progress})>"