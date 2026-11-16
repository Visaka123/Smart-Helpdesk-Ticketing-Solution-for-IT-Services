from sqlalchemy import Column, Integer, String, DateTime, Boolean, func
from app.database.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password = Column(String(255), nullable=False)
    role = Column(String(50), default="employee")  # employee, agent, manager, admin
    department = Column(String(100), default="General")  # e.g., Engineering, HR, Sales, IT, Finance
    assigned_team = Column(String(100), nullable=True)  # e.g., Network Team, IT Support, Database Team
    timezone = Column(String(50), default="Asia/Kolkata") # default to Asia/Kolkata
    max_open_tickets = Column(Integer, default=10)        # configurable ticket cap per agent
    is_demo = Column(Boolean, default=False, nullable=True)
    created_at = Column(DateTime, default=func.now())