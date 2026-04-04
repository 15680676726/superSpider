# -*- coding: utf-8 -*-
from __future__ import annotations

from collections import Counter
from typing import Any


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class DonorPackageService:
    def __init__(self, *, donor_service: object) -> None:
        self._donor_service = donor_service

    def list_packages(
        self,
        *,
        donor_id: str | None = None,
        limit: int | None = None,
    ) -> list[object]:
        lister = getattr(self._donor_service, "list_packages", None)
        if not callable(lister):
            return []
        return list(lister(donor_id=donor_id, limit=limit))

    def list_donor_packages(
        self,
        *,
        donor_id: str | None,
        limit: int | None = None,
    ) -> list[object]:
        return self.list_packages(donor_id=donor_id, limit=limit)

    def find_reusable_package(
        self,
        *,
        canonical_package_id: str | None = None,
        package_ref: str | None = None,
        package_version: str | None = None,
    ) -> object | None:
        normalized_canonical = _string(canonical_package_id)
        normalized_ref = _string(package_ref)
        normalized_version = _string(package_version)
        for item in self.list_packages(limit=None):
            if (
                normalized_canonical is not None
                and _string(getattr(item, "canonical_package_id", None)) == normalized_canonical
            ):
                return item
            if (
                _string(getattr(item, "package_ref", None)) == normalized_ref
                and _string(getattr(item, "package_version", None)) == normalized_version
            ):
                return item
        return None

    def summarize_packages(self) -> dict[str, Any]:
        packages = self.list_packages(limit=None)
        package_kind_count = dict(
            sorted(
                Counter(
                    (_string(getattr(item, "package_kind", None)) or "unknown")
                    for item in packages
                ).items(),
            ),
        )
        donor_ids = {
            donor_id
            for donor_id in (_string(getattr(item, "donor_id", None)) for item in packages)
            if donor_id is not None
        }
        return {
            "package_count": len(packages),
            "donor_count": len(donor_ids),
            "package_kind_count": package_kind_count,
        }


__all__ = ["DonorPackageService"]
