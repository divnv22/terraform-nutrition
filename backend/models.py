from sqlalchemy import Column, Integer, String, Float

from backend.database import Base


class DailyEntry(Base):
    __tablename__ = "daily_entries"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(String, nullable=False)
    weight = Column(Float, nullable=True)
    glucose = Column(Float, nullable=True)
    notes = Column(String, nullable=True)