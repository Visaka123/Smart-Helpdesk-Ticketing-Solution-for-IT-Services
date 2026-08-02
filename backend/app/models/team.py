from sqlalchemy import Column, Integer, String, Float, ForeignKey
from app.database.database import Base

class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True)
    manager_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    manager_name = Column(String(100), nullable=True)
    manager_email = Column(String(100), nullable=True)

    # Configurable SLA response & resolution hours per priority
    sla_response_hours_critical = Column(Float, default=2.0)
    sla_resolve_hours_critical = Column(Float, default=8.0)
    sla_response_hours_high = Column(Float, default=4.0)
    sla_resolve_hours_high = Column(Float, default=24.0)
    sla_response_hours_medium = Column(Float, default=8.0)
    sla_resolve_hours_medium = Column(Float, default=48.0)
    sla_response_hours_low = Column(Float, default=24.0)
    sla_resolve_hours_low = Column(Float, default=72.0)