"""Base class for the engine's tables, all in the `engine` Postgres schema.

There are no tables yet: feature 31 adds the first ones.
"""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

SCHEMA = "engine"


class Base(DeclarativeBase):
    metadata = MetaData(schema=SCHEMA)
