from sqlalchemy import Column, Integer, String, ForeignKey, Enum, DateTime, Float, Text
from sqlalchemy.orm import relationship
from .base import BaseModel
from .file import File
from .pickup_code import PickupCode

class FileUpload(BaseModel):
    """文件上传到服务器的过程记录表"""
    __tablename__ = "file_uploads"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="上传记录ID")
    file_id = Column(
        Integer,
        ForeignKey("files.id", ondelete="CASCADE"),
        nullable=False,
        comment="关联文件ID"
    )
    code = Column(
        String(6),
        ForeignKey("pickup_codes.code", ondelete="CASCADE"),
        nullable=False,
        comment="关联取件码（上传时绑定的取件码）"
    )
    uploader_ip = Column(String(45), comment="上传者IP地址")
    status = Column(
        Enum("pending", "uploading", "completed", "failed"),
        default="pending",
        comment="上传状态：等待中/上传中/完成/失败"
    )
    progress = Column(Float, default=0.0, comment="上传进度（0.0-100.0）")
    error_msg = Column(Text, comment="上传失败时的错误信息")
    completed_at = Column(DateTime, comment="上传完成时间")

    # 关联关系
    file = relationship("File", backref="uploads")
    pickup_code = relationship("PickupCode", backref="file_uploads")

    def __repr__(self):
        return f"<FileUpload(file_id={self.file_id}, code={self.code}, status={self.status})>"