from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import SystemComponent
from app.repositories.system_component_repository import (
    DuplicateCodeRepoError,
    SqlAlchemyCodeRepoRepository,
)


def test_code_repo_repository_create_list_get() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = testing_session_local()
    try:
        sc = SystemComponent(name="comp-a", description=None)
        db.add(sc)
        db.commit()
        db.refresh(sc)

        repo = SqlAlchemyCodeRepoRepository(db)
        created = repo.create(
            system_component_id=sc.id,
            provider="github",
            name="payment-api",
            url="https://github.com/org/payment-api",
            default_branch="main",
        )
        assert created.id is not None

        listed = repo.list()
        assert len(listed) == 1

        fetched = repo.get_by_id(created.id)
        assert fetched is not None
        assert fetched.id == created.id

        by_component = repo.list_by_system_component(sc.id)
        assert len(by_component) == 1
    finally:
        db.close()


def test_code_repo_repository_duplicate_name_provider_raises_error() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = testing_session_local()
    try:
        sc = SystemComponent(name="comp-a", description=None)
        db.add(sc)
        db.commit()
        db.refresh(sc)

        repo = SqlAlchemyCodeRepoRepository(db)
        repo.create(
            system_component_id=sc.id,
            provider="github",
            name="payment-api",
            url="https://github.com/org/payment-api",
            default_branch="main",
        )

        try:
            repo.create(
                system_component_id=sc.id,
                provider="github",
                name="payment-api",
                url="https://github.com/org/payment-api-2",
                default_branch="main",
            )
            assert False, "Expected DuplicateCodeRepoError"
        except DuplicateCodeRepoError:
            assert True
    finally:
        db.close()
