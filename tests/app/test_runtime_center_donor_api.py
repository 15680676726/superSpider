# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.routers.runtime_center import router as runtime_center_router


class _FakeStateQueryService:
    def list_capability_packages(self, *, limit: int | None = None):
        return [
            {
                "package_id": "package-1",
                "donor_id": "donor-1",
                "package_kind": "skill",
            },
        ][: limit or 20]

    def list_capability_trust_records(self, *, limit: int | None = None):
        return [
            {
                "donor_id": "donor-1",
                "trust_status": "trusted",
                "trial_success_count": 3,
            },
        ][: limit or 20]

    def get_capability_scout_summary(self):
        return {
            "status": "ready",
            "last_mode": "opportunity",
            "imported_candidate_count": 2,
        }


def test_runtime_center_donor_routes_expose_packages_trust_and_scout() -> None:
    app = FastAPI()
    app.include_router(runtime_center_router)
    app.state.state_query_service = _FakeStateQueryService()
    client = TestClient(app)

    packages = client.get("/runtime-center/capabilities/packages")
    trust = client.get("/runtime-center/capabilities/trust")
    scout = client.get("/runtime-center/capabilities/scout")

    assert packages.status_code == 200
    assert packages.json()[0]["package_id"] == "package-1"
    assert trust.status_code == 200
    assert trust.json()[0]["trust_status"] == "trusted"
    assert scout.status_code == 200
    assert scout.json()["status"] == "ready"
