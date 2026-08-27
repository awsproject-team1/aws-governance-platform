"""Control registry; Control remains a grouping key, never a merged verdict."""

from __future__ import annotations

from packages.contracts.governance import Control

from ..errors import GovernanceConflictError, GovernanceNotFoundError


class ControlRegistry:
    def __init__(self, controls: tuple[Control, ...] | list[Control] = ()) -> None:
        self._controls: dict[str, Control] = {}
        for control in controls:
            self.add(control)

    def add(self, control: Control) -> None:
        if control.control_key in self._controls:
            raise GovernanceConflictError(f"duplicate control_key: {control.control_key}")
        self._controls[control.control_key] = control

    def get(self, control_key: str) -> Control:
        try:
            return self._controls[control_key]
        except KeyError as exc:
            raise GovernanceNotFoundError(f"unknown control_key: {control_key}") from exc

    def contains(self, control_key: str) -> bool:
        return control_key in self._controls

    def list(self) -> tuple[Control, ...]:
        return tuple(self._controls[key] for key in sorted(self._controls))
