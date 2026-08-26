"""Private invocation probe for validating the staged backend package.

This module is not a product Lambda handler and must not be referenced by infrastructure.
"""


def invoke(_event: object, _context: object) -> None:
    """Exercise the framework-free invocation boundary without defining an API contract."""
