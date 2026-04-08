from dataclasses import dataclass

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.dependencies import get_render_logs_connector, get_render_runtime_connector
from app.models import IntegrationTargetMapping, SystemComponent
from app.repositories import (
    SqlAlchemyIntegrationTargetMappingRepository,
)


def build_db():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    testing_session_local = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    Base.metadata.create_all(bind=engine)
    return testing_session_local()


def test_repository_lists_active_mappings_with_environment_fallback() -> None:
    db = build_db()
    repo = SqlAlchemyIntegrationTargetMappingRepository(db)
    try:
        component_default = SystemComponent(name="default-service", description=None)
        component_staging = SystemComponent(name="staging-service", description=None)
        component_global = SystemComponent(name="global-service", description=None)
        db.add_all([component_default, component_staging, component_global])
        db.commit()
        db.refresh(component_default)
        db.refresh(component_staging)
        db.refresh(component_global)

        db.add_all(
            [
                IntegrationTargetMapping(
                    connector_name="render-runtime",
                    external_target_id="srv-123",
                    system_component_id=component_default.id,
                    environment="",
                    is_active=True,
                ),
                IntegrationTargetMapping(
                    connector_name="render-runtime",
                    external_target_id="srv-123",
                    system_component_id=component_staging.id,
                    environment="staging",
                    is_active=True,
                ),
                IntegrationTargetMapping(
                    connector_name="render-runtime",
                    external_target_id="srv-456",
                    system_component_id=component_global.id,
                    environment="",
                    is_active=True,
                ),
                IntegrationTargetMapping(
                    connector_name="render-runtime",
                    external_target_id="srv-789",
                    system_component_id=component_global.id,
                    environment="staging",
                    is_active=False,
                ),
                IntegrationTargetMapping(
                    connector_name="github",
                    external_target_id="acme/payment-api",
                    system_component_id=component_default.id,
                    environment="staging",
                    is_active=True,
                ),
            ]
        )
        db.commit()

        mappings = repo.list_active_target_component_mappings(
            connector_name="render-runtime",
            environment="staging",
        )
        mapping_by_target = {
            item.external_target_id: item.system_component_name for item in mappings
        }

        assert mapping_by_target == {
            "srv-123": "staging-service",
            "srv-456": "global-service",
        }
    finally:
        db.close()


def test_get_render_runtime_connector_reads_target_mapping_from_repository(
    monkeypatch,
) -> None:
    @dataclass(frozen=True)
    class FakeMapping:
        external_target_id: str
        system_component_name: str

    class FakeMappingRepository:
        def __init__(self) -> None:
            self.calls = []

        def list_active_target_component_mappings(
            self, connector_name: str, environment: str | None = None
        ):
            self.calls.append(
                {
                    "connector_name": connector_name,
                    "environment": environment,
                }
            )
            return [
                FakeMapping(
                    external_target_id="srv-123",
                    system_component_name="micro-cardservice",
                ),
                FakeMapping(
                    external_target_id="srv-456",
                    system_component_name="micro-ledger",
                ),
            ]

    mapping_repo = FakeMappingRepository()
    monkeypatch.setenv("RENDER_RUNTIME_ENVIRONMENT", "staging")
    monkeypatch.setenv("RENDER_API_KEY", "token")
    monkeypatch.setenv("RENDER_TIMEOUT_SECONDS", "7")
    monkeypatch.setenv("RENDER_SERVICE_IDS", "srv-legacy")
    monkeypatch.setenv("RENDER_SERVICE_COMPONENT_MAP", "srv-legacy:legacy-component")

    connector = get_render_runtime_connector(mapping_repository=mapping_repo)

    assert mapping_repo.calls == [
        {"connector_name": "render-runtime", "environment": "staging"}
    ]
    assert connector.service_ids == ["srv-123", "srv-456"]
    assert connector.service_component_map == {
        "srv-123": "micro-cardservice",
        "srv-456": "micro-ledger",
    }
    assert connector.environment == "staging"


def test_get_render_logs_connector_uses_resource_id_env_fallback_when_no_mapping(
    monkeypatch,
) -> None:
    class FakeMappingRepository:
        def list_active_target_component_mappings(
            self, connector_name: str, environment: str | None = None
        ):
            return []

    mapping_repo = FakeMappingRepository()
    monkeypatch.setenv("RENDER_RUNTIME_ENVIRONMENT", "staging")
    monkeypatch.setenv("RENDER_API_KEY", "token")
    monkeypatch.setenv("RENDER_OWNER_ID", "tea-owner")
    monkeypatch.setenv("RENDER_LOGS_RESOURCE_ID", "srv-fallback")
    monkeypatch.setenv("RENDER_TIMEOUT_SECONDS", "7")
    monkeypatch.delenv("RENDER_LOGS_SOURCE", raising=False)

    connector = get_render_logs_connector(mapping_repository=mapping_repo)

    assert connector.service_component_map == {"srv-fallback": "srv-fallback"}
    assert connector.owner_id == "tea-owner"
    assert connector.environment == "staging"
