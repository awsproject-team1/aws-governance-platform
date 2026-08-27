"""Conceptual Global Source composition before production Profile IDs are named.

The executable ``PolicyProfile`` continues to pin approved Rule versions. This module
only validates which Global Sources may contribute those Rules for a customer context;
it does not invent Profile IDs or add a mapping-only framework to an Assessment.
"""

from __future__ import annotations

from collections.abc import Iterable

from ..errors import GovernanceValidationError
from ..sources.catalog import GlobalSourceCatalog, GlobalSourceDefinition, GlobalSourceRole


def select_global_profile_sources(
    catalog: GlobalSourceCatalog,
    requested_source_ids: Iterable[str],
    customer_capabilities: Iterable[str] = (),
) -> tuple[GlobalSourceDefinition, ...]:
    capabilities = tuple(customer_capabilities)
    selected: list[GlobalSourceDefinition] = []
    seen: set[str] = set()
    for source_id in requested_source_ids:
        if source_id in seen:
            raise GovernanceValidationError(f"duplicate Profile Source: {source_id}")
        seen.add(source_id)
        definition = catalog.get(source_id)
        if definition.role is GlobalSourceRole.MAPPING_EVIDENCE:
            raise GovernanceValidationError(
                f"mapping/evidence Source cannot enter an Assessment Profile: {source_id}"
            )
        applicability = catalog.applicability(source_id, capabilities)
        if not applicability.applicable:
            raise GovernanceValidationError(
                f"Global Source is not applicable: {source_id}; missing "
                + ", ".join(applicability.missing_capabilities)
            )
        selected.append(definition)
    return tuple(sorted(selected, key=lambda item: item.source_id))


def default_global_profile_candidates(
    catalog: GlobalSourceCatalog,
) -> tuple[GlobalSourceDefinition, ...]:
    """Reference-level candidates; approved Rule pins are still required."""
    return catalog.default_profile_candidates()
