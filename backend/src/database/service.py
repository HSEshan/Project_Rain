from sqlalchemy.ext.asyncio import AsyncSession
from src.database.core import db_dependency


class BaseService:
    def __init__(self, db: AsyncSession = db_dependency):
        self.db = db
