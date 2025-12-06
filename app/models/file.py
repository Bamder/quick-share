from sqlalchemy import Column, Integer, String, BigInteger
from .base import BaseModel

class File(BaseModel):
    """文件基础信息表"""
    __tablename__ = "files"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="文件唯一ID")
    original_name = Column(String(255), nullable=False, comment="文件原始名称")
    stored_name = Column(String(36), nullable=False, comment="存储用UUID文件名")
    size = Column(BigInteger, nullable=False, comment="文件大小（字节）")
    hash = Column(String(64), comment="文件SHA256哈希")
    mime_type = Column(String(100), comment="文件MIME类型")

    # 若需自定义字符串展示
    def __repr__(self):
        return f"<File(id={self.id}, original_name={self.original_name})>"