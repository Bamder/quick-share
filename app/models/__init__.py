"""模型统一导出入口，供Alembic和业务代码调用"""
from .base import Base
from .file import File
from .pickup_code import PickupCode
from .webrtc_session import WebRTCSession
from .report import Report
from .registered_sender import RegisteredSender  # 新增
from .file_upload import FileUpload
from .file_transfer import FileTransfer
from .file_storage import FileStorage  # 若启用了该可选表
# 暴露所有模型类，便于Alembic自动生成迁移脚本
__all__ = ["Base",
           "File",
           "PickupCode",
           "WebRTCSession",
           "Report",
           "RegisteredSender",
           "FileUpload",
           "FileTransfer",
           "FileStorage"]