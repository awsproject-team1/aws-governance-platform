"""Validated Policy Source/Resource/Control mappings."""

from __future__ import annotations

from packages.contracts.governance import SourceControlMapping, SourceReference, SourceType

from ..controls.registry import ControlRegistry
from ..errors import GovernanceConflictError, GovernanceNotFoundError
from ..sources.registry import PolicySourceRegistry


class SourceControlMappingRegistry:
    def __init__(
        self,
        controls: ControlRegistry,
        sources: PolicySourceRegistry,
        mappings: tuple[SourceControlMapping, ...] | list[SourceControlMapping] = (),
    ) -> None:
        self._controls = controls
        self._sources = sources
        self._mappings: dict[tuple[tuple[str, str, str, str], str, str], SourceControlMapping] = {}
        for mapping in mappings:
            self.add(mapping)

    @staticmethod
    def _key(mapping: SourceControlMapping) -> tuple[tuple[str, str, str, str], str, str]:
        return (mapping.source_reference.identity, mapping.resource_type, mapping.control_key)

    def add(self, mapping: SourceControlMapping) -> None:
        self._controls.get(mapping.control_key)
        self._sources.require_reference(mapping.source_reference)
        key = self._key(mapping)
        if key in self._mappings:
            raise GovernanceConflictError("duplicate source/resource/control mapping")
        self._mappings[key] = mapping

    def require(
        self, source_reference: SourceReference, resource_type: str, control_key: str
    ) -> None:
        key = (source_reference.identity, resource_type, control_key)
        if key not in self._mappings:
            raise GovernanceNotFoundError(
                "source reference is not mapped to the rule resource/control"
            )

    def allows_reference(self, source_reference: SourceReference) -> bool:
        return any(key[0] == source_reference.identity for key in self._mappings)

    def source_type(self, source_reference: SourceReference) -> SourceType:
        return self._sources.require_reference(source_reference).source_type

    def list(self) -> tuple[SourceControlMapping, ...]:
        return tuple(self._mappings[key] for key in sorted(self._mappings))
