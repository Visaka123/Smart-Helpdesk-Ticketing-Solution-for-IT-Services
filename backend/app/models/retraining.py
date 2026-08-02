from sqlalchemy import Column, Integer, String, Float, DateTime, func
from app.database.database import Base

class RetrainingLog(Base):
    __tablename__ = "retraining_logs"

    id = Column(Integer, primary_key=True, index=True)
    model_type = Column(String(50), nullable=False)  # routing, priority
    version = Column(String(50), nullable=False)
    samples_count = Column(Integer, default=0)
    accuracy = Column(Float, default=0.0)
    f1_score = Column(Float, default=0.0)
    created_at = Column(DateTime, default=func.now())
