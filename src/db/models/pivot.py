# 1. --- SQLAlchemy Pivot Model ---
# File: src/db/models/pivot.py

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, Boolean, Enum, Integer
from sqlalchemy.dialects.postgresql import UUID
from src.db.base import Base

class Pivot(Base):
    __tablename__ = "pivot"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol = Column(String, index=True)
    timeframe = Column(String)
    timestamp = Column(DateTime)
    index = Column(Integer)  # index in candle array if useful

    price = Column(Float)
    type = Column(Enum("high", "low", name="pivot_type"))
    confirmed = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
