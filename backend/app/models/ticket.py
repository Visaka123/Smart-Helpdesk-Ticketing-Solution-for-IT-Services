from sqlalchemy import Column, Integer, String, Text, Float, DateTime, Boolean, ForeignKey, func
from sqlalchemy.orm import relationship
from app.database.database import Base

class TicketRequester(Base):
    __tablename__ = "ticket_requesters"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    requester_name = Column(String(100), nullable=False)
    requester_department = Column(String(100), default="General")
    linked_at = Column(DateTime, default=func.now())
    link_reason = Column(String(100), default="hard_blocked_auto_linked")

    ticket = relationship("Ticket", back_populates="requesters")

class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(100), default="General IT")
    
    # Priority fields
    priority = Column(String(50), default="Medium")  # Low, Medium, High, Critical
    priority_confidence = Column(Float, default=1.0)
    
    # Status & Routing
    status = Column(String(50), default="open")  # open, in_progress, pending, resolved, closed
    assigned_team = Column(String(100), default="Unassigned/Triage")
    assigned_agent_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    assigned_agent_name = Column(String(100), nullable=True)
    routing_confidence = Column(Float, default=1.0)
    top_alternative_teams = Column(Text, nullable=True)  # JSON formatted list
    is_low_confidence_routed = Column(Boolean, default=False)
    
    # Duplicate detection, Linking & Structured Resolution
    similarity_score = Column(Float, default=0.0)
    parent_ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=True)
    related_ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=True)
    
    # Structured resolution capture (Summary + Detail)
    resolution_notes = Column(Text, nullable=True)     # Legacy/compatibility field
    resolution_summary = Column(Text, nullable=True)   # Non-technical, user-facing summary
    resolution_detail = Column(Text, nullable=True)    # Technical steps, configs, PRs, diffs
    root_cause = Column(String(100), nullable=True)    # Hardware, Software, Network, User Error, Permission
    
    # Requester info
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    requester_name = Column(String(100), nullable=True)
    requester_department = Column(String(100), nullable=True)
    
    # Requesters relationship (1 master ticket can have multiple linked requesters)
    requesters = relationship("TicketRequester", back_populates="ticket", cascade="all, delete-orphan")
    
    # Satisfaction rating & feedback
    satisfaction_rating = Column(Integer, nullable=True)  # 1 to 5
    satisfaction_feedback = Column(Text, nullable=True)

    # Timestamps & SLA
    created_at = Column(DateTime, default=func.now())
    sla_due_at = Column(DateTime, nullable=True)
    first_responded_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    is_sla_breached = Column(Boolean, default=False)
    escalated_to_manager = Column(Boolean, default=False)
    escalated_at = Column(DateTime, nullable=True)