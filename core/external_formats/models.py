"""Shared result contracts for external asset imports."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class ExternalFormatError(ValueError):
    """Raised when an uploaded file cannot be safely interpreted."""


@dataclass
class ImportPreview:
    asset_type: str
    source_format: str
    source_version: str
    suggested_name: str
    mapped_asset: dict[str, Any]
    mapped_fields: list[str] = field(default_factory=list)
    degraded_fields: list[str] = field(default_factory=list)
    preserved_fields: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    portrait_bytes: bytes | None = field(default=None, repr=False)

    def to_dict(self, *, include_asset: bool = False) -> dict[str, Any]:
        result = {
            "asset_type": self.asset_type,
            "source_format": self.source_format,
            "source_version": self.source_version,
            "suggested_name": self.suggested_name,
            "mapped_fields": self.mapped_fields,
            "degraded_fields": self.degraded_fields,
            "preserved_fields": self.preserved_fields,
            "warnings": self.warnings,
            "has_portrait": self.portrait_bytes is not None,
        }
        if include_asset:
            result["mapped_asset"] = self.mapped_asset
        return result
