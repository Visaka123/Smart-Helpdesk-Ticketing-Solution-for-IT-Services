from app.database.database import engine

from app.models.user import User
from app.models.ticket import Ticket
from app.models.team import Team
from app.models.knowledge import KnowledgeArticle

from app.database.database import Base

Base.metadata.create_all(bind=engine)

print("Tables Created")