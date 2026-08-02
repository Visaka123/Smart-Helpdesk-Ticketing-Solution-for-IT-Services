from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, func
from app.database.database import Base

class SLAEscalationLog(Base):
    __tablename__ = "sla_escalation_logs"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False, index=True)
    team_name = Column(String(100), nullable=False)
    manager_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    manager_name = Column(String(100), nullable=True)
    agent_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    agent_name = Column(String(100), nullable=True)
    escalation_reason = Column(String(50), nullable=False)  # AT_RISK_80%, BREACHED_100%, MANUAL
    time_overdue_minutes = Column(Float, default=0.0)
    created_at = Column(DateTime, default=func.now())
