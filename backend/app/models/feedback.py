from sqlalchemy import Column, Integer, String, Text, Float, DateTime, func
from app.database.database import Base

class DuplicateFeedbackLog(Base):
    __tablename__ = "duplicate_feedback_logs"

    id = Column(Integer, primary_key=True, index=True)
    new_ticket_text = Column(Text, nullable=False)
    matched_ticket_id = Column(Integer, nullable=True)
    similarity_score = Column(Float, default=0.0)
    user_action = Column(String(50), nullable=False)  # accepted_solution, rejected_created_ticket
    created_at = Column(DateTime, default=func.now())
