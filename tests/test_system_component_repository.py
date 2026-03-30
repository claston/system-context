from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.repositories.system_component_repository import (
    DuplicateSystemComponentNameError,
    SqlAlchemySystemComponentRepository,
)


def test_repository_create_list_get() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    testing_session_local = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    Base.metadata.create_all(bind=engine)

    db = testing_session_local()
    try:
        repo = SqlAlchemySystemComponentRepository(db)

        created = repo.create(name="payment-api", description="Handles payments")
        assert created.id is not None
        assert created.name == "payment-api"

        listed = repo.list()
        assert len(listed) == 1
        assert listed[0].name == "payment-api"

        fetched = repo.get_by_id(created.id)
        assert fetched is not None
        assert fetched.id == created.id
    finally:
        db.close()


def test_repository_duplicate_name_raises_domain_error() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    testing_session_local = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    Base.metadata.create_all(bind=engine)

    db = testing_session_local()
    try:
        repo = SqlAlchemySystemComponentRepository(db)
        repo.create(name="payment-api", description="A")

        try:
            repo.create(name="payment-api", description="B")
            assert False, "Expected DuplicateSystemComponentNameError"
        except DuplicateSystemComponentNameError:
            assert True
    finally:
        db.close()
