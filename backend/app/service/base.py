from app.database.core import db_dependency
from sqlalchemy.ext.asyncio import AsyncSession


class BaseService:
    def __init__(self, db: AsyncSession = db_dependency):
        self.db = db
