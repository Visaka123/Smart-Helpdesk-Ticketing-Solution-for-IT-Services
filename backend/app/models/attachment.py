from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.database.database import Base

class TicketAttachment(Base):
    __tablename__ = "ticket_attachments"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)           # Stored disk filename
    original_filename = Column(String(255), nullable=False)  # Original user-supplied filename
    file_size = Column(Integer, nullable=False)              # Size in bytes
    content_type = Column(String(100), nullable=True)        # MIME type
    file_path = Column(String(500), nullable=False)          # Path / key relative to attachments storage
    uploaded_by = Column(String(100), nullable=True)         # Name of requester or agent
    created_at = Column(DateTime, default=func.now())

    ticket = relationship("Ticket", back_populates="attachments")
