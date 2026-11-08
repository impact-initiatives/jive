from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum, auto
from pathlib import Path
from typing import Any

from argus.locales.il8n import _


class SeverityLevel(StrEnum):
    INFO = auto()
    WARNING = auto()
    ERROR = auto()
    ADMIN_ERROR = auto()
    PASSED = auto()
    ADMIN_INFO = auto()


@dataclass(slots=True)
class ValidationResult:
    rule: str
    message: str
    severity: SeverityLevel
    sheet_name: str | None = None
    column_name: str | None = None
    details: dict[str, Any] | None = None


class BaseValidator(ABC):
    """Abstract base class for all validators."""

    @abstractmethod
    def validate(self, data: Any, **kwargs: str | int | float | Path) -> list[ValidationResult]:
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    def _(self, key: str, **kwargs: str | int | float):
        return _(key, **kwargs)


@dataclass(slots=True)
class SortedSheets:
    cleaning_log_sheets: list[str] = field(default_factory=list)
    deletion_log_sheets: list[str] = field(default_factory=list)
    clean_sheets: list[str] = field(default_factory=list)
    raw_sheets: list[str] = field(default_factory=list)
    unknown_sheets: list[str] = field(default_factory=list)
