from app.core.config import Settings
from app.core.db import create_session_factory


def test_session_factory_uses_configured_database_url() -> None:
    settings = Settings(
        environment="test",
        database_url="postgresql+psycopg://user:password@database.example/rfp_test",
    )

    factory = create_session_factory(settings)
    engine = factory.kw["bind"]

    assert engine.url.drivername == "postgresql+psycopg"
    assert engine.url.host == "database.example"
    assert engine.url.database == "rfp_test"
