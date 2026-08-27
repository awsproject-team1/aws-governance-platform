"""Policy Source identity and version registry."""

from __future__ import annotations

from packages.contracts.governance import PolicySource, SourceReference

from ..errors import GovernanceConflictError, GovernanceNotFoundError, GovernanceValidationError


class PolicySourceRegistry:
    def __init__(self, sources: tuple[PolicySource, ...] | list[PolicySource] = ()) -> None:
        self._sources: dict[tuple[str, str], PolicySource] = {}
        for source in sources:
            self.add(source)

    def add(self, source: PolicySource) -> None:
        key = (source.source_id, source.source_version)
        if key in self._sources:
            raise GovernanceConflictError(
                f"duplicate policy source version: {source.source_id}@{source.source_version}"
            )
        existing_types = {
            item.source_type
            for (source_id, _), item in self._sources.items()
            if source_id == source.source_id
        }
        if existing_types and source.source_type not in existing_types:
            raise GovernanceValidationError(
                "all versions of one policy source must keep the same source_type"
            )
        self._sources[key] = source

    def get(self, source_id: str, source_version: str) -> PolicySource:
        try:
            return self._sources[(source_id, source_version)]
        except KeyError as exc:
            raise GovernanceNotFoundError(
                f"unknown policy source version: {source_id}@{source_version}"
            ) from exc

    def require_reference(self, reference: SourceReference) -> PolicySource:
        return self.get(reference.document_id, reference.document_version)

    def versions_of(self, source_id: str) -> tuple[str, ...]:
        return tuple(sorted(version for item_id, version in self._sources if item_id == source_id))

    def list(self) -> tuple[PolicySource, ...]:
        return tuple(self._sources[key] for key in sorted(self._sources))
