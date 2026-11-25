from abc import ABC, abstractmethod
from collections.abc import Generator
from contextlib import contextmanager
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


class ValidatorResult(StrEnum):
    MISSING_COMPONENTS = auto()
    RUN_SUCCESSFULLY = auto()
    PASSED = auto()
    PENDING = auto()
    ORCHESTRATOR_ERROR = auto()


@dataclass(slots=True)
class ValidationResult:
    message: str
    severity: SeverityLevel
    sheet_name: str | None = None
    column_name: str | None = None
    details: dict[str, Any] | None = None

    def get_details_length(self, default_return_value: int = 1) -> int:
        """Number of row-level findings; the default represents "one issue: the message"."""
        if self.details is None:
            return default_return_value
        first_value = next(iter(self.details.values()), None)
        if first_value is None:
            return default_return_value
        try:
            return len(first_value)
        except TypeError:  # scalar value with no len()
            return default_return_value


@dataclass(slots=True)
class ValidatorResponse:
    name: str
    details: list[ValidationResult] = field(default_factory=list)
    result: ValidatorResult = ValidatorResult.PENDING
    # could add importance


class MissingComponents(Exception):
    def __init__(self, details: list[ValidationResult]):
        self.details = details


class BaseValidator(ABC):
    """Abstract base class for all validators."""

    @abstractmethod
    def validate(self, data: Any, **kwargs: str | int | float | Path) -> ValidatorResponse:
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    def _(self, key: str, **kwargs: str | int | float):
        return _(key, **kwargs)

    @contextmanager
    def _validation(self) -> Generator[ValidatorResponse]:
        response = ValidatorResponse(name=self.name)
        try:
            yield response
            response.result = ValidatorResult.RUN_SUCCESSFULLY
        except MissingComponents as exc:
            response.details.extend(exc.details)
            response.result = ValidatorResult.MISSING_COMPONENTS


@dataclass(slots=True)
class SortedSheets:
    cleaning_log_sheets: list[str] = field(default_factory=list)
    deletion_log_sheets: list[str] = field(default_factory=list)
    clean_sheets: list[str] = field(default_factory=list)
    raw_sheets: list[str] = field(default_factory=list)
    unknown_sheets: list[str] = field(default_factory=list)
