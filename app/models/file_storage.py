from sqlalchemy import Column, Integer, Boolean, String, ForeignKey
from sqlalchemy.orm import relationship
from .base import BaseModel
from .file import File

class FileStorage(BaseModel):
    """文件存储详情表"""
    __tablename__ = "file_storages"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="存储记录ID")
    file_id = Column(
        Integer,
        ForeignKey("files.id", ondelete="CASCADE"),
        nullable=False,
        comment="关联文件ID"
    )
    storage_path = Column(String(500), nullable=False, comment="文件在服务器的存储路径")
    storage_node = Column(String(100), comment="存储节点标识（如多服务器部署时）")
    is_valid = Column(Boolean, default=True, comment="存储文件是否有效")

    # 关联文件
    file = relationship("File", backref="storages")

    def __repr__(self):
        return f"<FileStorage(file_id={self.file_id}, path={self.storage_path})>"