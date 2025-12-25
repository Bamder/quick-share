from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, ForeignKey, Enum
from sqlalchemy.orm import relationship
from .base import BaseModel


class RegisteredSender(BaseModel):
    __tablename__ = 'registered_senders'

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(6), ForeignKey('pickup_codes.code'), nullable=False)
    session_id = Column(String(64))
    sender_info = Column(JSON)
    callback_url = Column(String(500))
    status = Column(Enum('waiting', 'notified', 'expired', name='sender_status'), nullable=False)
    expires_at = Column(DateTime, nullable=False)

    # 如果需要关系，可以添加（可选）
    # pickup_code = relationship("PickupCode", back_populates="registered_senders")