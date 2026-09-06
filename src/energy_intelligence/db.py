from sqlalchemy import create_engine

from energy_intelligence.settings import settings


def engine():
    return create_engine(settings.database_url, future=True)
