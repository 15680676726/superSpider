# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Iterable

from .models import DiscoveryHit, NormalizedDiscoveryHit, _unique_strings


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _slug(value: object | None) -> str:
    text = (_string(value) or "unknown").lower()
    slug: list[str] = []
    for char in text:
        if char.isalnum():
            slug.append(char)
        elif slug and slug[-1] != "-":
            slug.append("-")
    return "".join(slug).strip("-") or "unknown"


def _source_level_identity(hit: DiscoveryHit) -> str:
    return "|".join(
        part
        for part in (
            _string(hit.canonical_package_id),
            _string(hit.candidate_source_lineage),
            _string(hit.candidate_source_ref),
            _string(hit.display_name),
        )
        if part is not None
    ) or "unknown"


def _overlap_score(left: DiscoveryHit, right: DiscoveryHit) -> float:
    left_keys = set(left.capability_keys)
    right_keys = set(right.capability_keys)
    if not left_keys or not right_keys:
        return 0.0
    shared = left_keys & right_keys
    if not shared:
        return 0.0
    union = left_keys | right_keys
    return len(shared) / max(1, len(union))


def _cluster_overlap_score(cluster: list[DiscoveryHit]) -> float:
    score = 0.0
    for index, left in enumerate(cluster):
        for right in cluster[index + 1 :]:
            score = max(score, _overlap_score(left, right))
    return score


def _shared_identity(left: DiscoveryHit, right: DiscoveryHit) -> bool:
    if (
        _string(left.canonical_package_id) is not None
        and _string(left.canonical_package_id) == _string(right.canonical_package_id)
    ):
        return True
    if (
        _string(left.candidate_source_lineage) is not None
        and _string(left.candidate_source_lineage)
        == _string(right.candidate_source_lineage)
    ):
        return True
    if (
        _string(left.equivalence_hint) is not None
        and _string(left.equivalence_hint) == _string(right.equivalence_hint)
    ):
        return True
    return left.candidate_kind == right.candidate_kind and _overlap_score(left, right) == 1.0


def _dedup_within_source(discovery_hits: Iterable[DiscoveryHit]) -> list[DiscoveryHit]:
    unique_hits: list[DiscoveryHit] = []
    seen: set[tuple[str, str]] = set()
    for hit in discovery_hits:
        key = (_string(hit.source_id) or "unknown-source", _source_level_identity(hit))
        if key in seen:
            continue
        seen.add(key)
        unique_hits.append(hit)
    return unique_hits


def _merge_clusters(discovery_hits: Iterable[DiscoveryHit]) -> list[list[DiscoveryHit]]:
    clusters: list[list[DiscoveryHit]] = [[hit] for hit in _dedup_within_source(discovery_hits)]
    merged = True
    while merged:
        merged = False
        for left_index in range(len(clusters)):
            if merged:
                break
            for right_index in range(left_index + 1, len(clusters)):
                if any(
                    _shared_identity(left_hit, right_hit)
                    for left_hit in clusters[left_index]
                    for right_hit in clusters[right_index]
                ):
                    clusters[left_index].extend(clusters.pop(right_index))
                    merged = True
                    break
    return clusters


def _normalized_source_kind(cluster: list[DiscoveryHit]) -> str:
    candidate_kind = cluster[0].candidate_kind.strip().lower()
    if candidate_kind == "mcp-bundle":
        return "external_catalog"
    return "external_remote"


def _equivalence_class(cluster: list[DiscoveryHit]) -> str:
    for hit in cluster:
        explicit = _string(hit.equivalence_hint)
        if explicit is not None:
            return explicit
    for hit in cluster:
        package_id = _string(hit.canonical_package_id)
        if package_id is not None:
            return package_id
    for hit in cluster:
        lineage = _string(hit.candidate_source_lineage)
        if lineage is not None:
            return lineage
    return f"equiv:{_slug(cluster[0].display_name or cluster[0].candidate_source_ref)}"


def _build_normalized_hit(cluster: list[DiscoveryHit]) -> NormalizedDiscoveryHit:
    preferred = cluster[0]
    canonical_package_id = next(
        (
            _string(hit.canonical_package_id)
            for hit in cluster
            if _string(hit.canonical_package_id) is not None
        ),
        None,
    )
    candidate_source_lineage = next(
        (
            _string(hit.candidate_source_lineage)
            for hit in cluster
            if _string(hit.candidate_source_lineage) is not None
        ),
        None,
    )
    source_aliases = _unique_strings(
        [hit.source_alias or hit.source_id for hit in cluster],
    )
    source_ids = _unique_strings([hit.source_id for hit in cluster])
    capability_keys = _unique_strings(
        [value for hit in cluster for value in hit.capability_keys],
    )
    overlap_score = _cluster_overlap_score(cluster)
    replacement_relation = next(
        (
            _string(hit.replacement_relation)
            for hit in cluster
            if _string(hit.replacement_relation) is not None
        ),
        None,
    )
    protocol_surface_kind = next(
        (
            _string(hit.protocol_surface_kind)
            for hit in cluster
            if _string(hit.protocol_surface_kind) is not None
        ),
        None,
    )
    transport_kind = next(
        (
            _string(hit.transport_kind)
            for hit in cluster
            if _string(hit.transport_kind) is not None
        ),
        None,
    )
    call_surface_ref = next(
        (
            _string(hit.call_surface_ref)
            for hit in cluster
            if _string(hit.call_surface_ref) is not None
        ),
        None,
    )
    formal_adapter_eligible = any(hit.formal_adapter_eligible for hit in cluster)
    adapter_blockers = _unique_strings(
        [value for hit in cluster for value in hit.adapter_blockers],
    )
    protocol_hints = next(
        (
            dict(hit.protocol_hints)
            for hit in cluster
            if isinstance(hit.protocol_hints, dict) and hit.protocol_hints
        ),
        {},
    )
    if replacement_relation is None and len(cluster) > 1 and overlap_score == 1.0:
        replacement_relation = "potential-equivalent"
    confidence_score = min(
        1.0,
        0.55
        + (0.15 * max(0, len(source_aliases) - 1))
        + (0.1 if canonical_package_id is not None else 0.0)
        + (0.1 if candidate_source_lineage is not None else 0.0),
    )
    metadata = {
        "raw_source_refs": [
            hit.candidate_source_ref
            for hit in cluster
            if _string(hit.candidate_source_ref) is not None
        ],
        "raw_source_kinds": list(_unique_strings([hit.source_kind for hit in cluster])),
    }
    return NormalizedDiscoveryHit(
        candidate_kind=preferred.candidate_kind,
        candidate_source_kind=_normalized_source_kind(cluster),
        display_name=_string(preferred.display_name),
        summary=str(preferred.summary or ""),
        candidate_source_ref=(
            _string(preferred.candidate_source_ref)
            or _string(preferred.display_name)
            or canonical_package_id
        ),
        candidate_source_version=_string(preferred.candidate_source_version),
        candidate_source_lineage=candidate_source_lineage,
        canonical_package_id=canonical_package_id,
        equivalence_class=_equivalence_class(cluster),
        source_aliases=source_aliases,
        source_ids=source_ids,
        capability_keys=capability_keys,
        capability_overlap_score=overlap_score,
        replacement_relation=replacement_relation,
        protocol_surface_kind=protocol_surface_kind,
        transport_kind=transport_kind,
        call_surface_ref=call_surface_ref,
        formal_adapter_eligible=formal_adapter_eligible,
        adapter_blockers=adapter_blockers,
        protocol_hints=protocol_hints,
        confidence_score=confidence_score,
        source_hit_count=len(cluster),
        metadata=metadata,
    )


def normalize_discovery_hits(
    discovery_hits: Iterable[DiscoveryHit],
) -> list[NormalizedDiscoveryHit]:
    return [
        _build_normalized_hit(cluster)
        for cluster in _merge_clusters(discovery_hits)
    ]


__all__ = ["normalize_discovery_hits"]
