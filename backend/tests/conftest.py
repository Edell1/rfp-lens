from collections.abc import Callable, Generator
import os

import psycopg
from psycopg import sql
import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.db.models import Base, User


TEST_DATABASE_URL = os.getenv(
    "RFP_LENS_TEST_DATABASE_URL",
    "postgresql+psycopg://rfp_lens:rfp_lens@localhost:5432/rfp_lens_test",
)


def _ensure_test_database(database_url: str) -> None:
    url = make_url(database_url)
    database_name = url.database
    if database_name is None:
        raise RuntimeError("Test database URL must include a database name")
    admin_url = url.set(database="postgres", drivername="postgresql")
    admin_dsn = admin_url.render_as_string(hide_password=False)
    with psycopg.connect(admin_dsn, autocommit=True) as connection:
        exists = connection.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (database_name,)
        ).fetchone()
        if exists is None:
            connection.execute(
                sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name))
            )


@pytest.fixture(scope="session")
def database_engine():
    _ensure_test_database(TEST_DATABASE_URL)
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(database_engine) -> Generator[Session, None, None]:
    connection = database_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()


@pytest.fixture
def user_factory(db_session: Session) -> Callable[[str], User]:
    def create_user(email: str) -> User:
        user = User(email=email, password_hash="not-a-real-password-hash")
        db_session.add(user)
        db_session.flush()
        return user

    return create_user
