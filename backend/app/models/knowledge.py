from sqlalchemy import Column, Integer, String, Text, DateTime, func
from app.database.database import Base

class KnowledgeArticle(Base):
    __tablename__ = "knowledge_articles"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    category = Column(String(100), default="General")
    content = Column(Text, nullable=False)
    source_file = Column(String(255), nullable=True)
    helpful_count = Column(Integer, default=0)
    unhelpful_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now())