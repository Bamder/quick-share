from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Enum
from sqlalchemy.orm import relationship
from .base import BaseModel
from .file import File

class PickupCode(BaseModel):
    """取件码表（关联文件，控制访问）"""
    __tablename__ = "pickup_codes"

    code = Column(String(12), primary_key=True, comment="12位取件码（前6位查找码+后6位密钥码，大写字母+数字）")
    file_id = Column(Integer, ForeignKey("files.id", ondelete="CASCADE"), nullable=False, comment="关联文件ID")
    status = Column(
        Enum("waiting", "transferring", "completed", "expired"),
        default="waiting",
        comment="取件码状态"
    )
    used_count = Column(Integer, default=0, comment="已使用次数")
    limit_count = Column(Integer, default=3, comment="最大使用次数（999=无限）")
    uploader_ip = Column(String(45), comment="上传者IP")
    expire_at = Column(DateTime, nullable=False, comment="过期时间")

    # 关联文件模型（ORM反向查询）
    file = relationship("File", backref="pickup_codes")

    def __repr__(self):
        return f"<PickupCode(code={self.code}, file_id={self.file_id}, status={self.status})>"