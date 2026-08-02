from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, func
from app.database.database import Base

class TicketComment(Base):
    __tablename__ = "ticket_comments"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    author_name = Column(String(100), nullable=False)
    author_role = Column(String(50), default="agent")  # employee, agent, manager
    content = Column(Text, nullable=False)
    is_internal = Column(Boolean, default=False)  # True for agent-only notes
    created_at = Column(DateTime, default=func.now())
