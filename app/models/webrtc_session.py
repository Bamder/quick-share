from sqlalchemy import Column, Integer, String, Text, ForeignKey, Enum, UniqueConstraint, JSON
from sqlalchemy.orm import relationship
from .base import BaseModel
from .pickup_code import PickupCode

class WebRTCSession(BaseModel):
    """WebRTC信令会话表（存储P2P连接数据）"""
    __tablename__ = "webrtc_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="会话ID")
    code = Column(
        String(6),
        ForeignKey("pickup_codes.code", ondelete="CASCADE"),
        nullable=False,
        comment="关联取件码"
    )
    session_id = Column(String(64), nullable=False, comment="WebRTC会话唯一标识")
    offer = Column(Text, comment="SDP Offer（分享方生成）")
    answer = Column(Text, comment="SDP Answer（领取方生成）")
    ice_candidates = Column(JSON, comment="ICE候选列表（MySQL5.7+）")
    status = Column(
        Enum("pending", "offer_created", "answer_received", "connected", "failed", "closed"),
        default="pending",
        comment="会话状态"
    )

    # 联合唯一索引（避免同一取件码+会话ID重复）
    __table_args__ = (
        UniqueConstraint("code", "session_id", name="uk_code_session"),
    )

    # 关联取件码模型
    pickup_code = relationship("PickupCode", backref="webrtc_sessions")

    def __repr__(self):
        return f"<WebRTCSession(code={self.code}, session_id={self.session_id}, status={self.status})>"