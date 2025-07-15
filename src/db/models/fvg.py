from src.db.base import Base
from sqlalchemy import Column, String, Float, Boolean, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID
import uuid

class FVG(Base):
    __tablename__ = "fvg"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol = Column(String, nullable=False)
    timeframe = Column(String, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    direction = Column(String, nullable=False)  # bullish / bearish
    zone_low = Column(Float, nullable=False)
    zone_high = Column(Float, nullable=False)

    status = Column(String, nullable=False)  # open, mitigated, invalidated, iFVG
    iFVG = Column(Boolean, default=False)
    touched = Column(Boolean, default=False)

    created_by_index = Column(Integer, nullable=True)
    mitigation_by = Column(Integer, nullable=True)
    invalidated_by = Column(Integer, nullable=True)

    mitigated_at = Column(DateTime, nullable=True)
    invalidated_at = Column(DateTime, nullable=True)
    retested = Column(Boolean, default=False)
    retested_at = Column(DateTime, nullable=True)

    penetration_pct = Column(Float, nullable=True)
    duration_open = Column(Integer, nullable=True)
    volume_at_creation = Column(Float, nullable=True)
