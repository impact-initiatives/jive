from typing import override

from ...loaders.base_excel_loader import ExcelLoaderData
from ..base import (
    BaseValidator,
    SeverityLevel,
    ValidationResult,
    ValidatorResponse,
)


class UnexpectedSheetsCheck(BaseValidator):
    @property
    @override
    def name(self) -> str:
        return "UnexpectedSheetsCheck"

    @override
    def validate(self, data: ExcelLoaderData, **kwargs: str | int | float) -> ValidatorResponse:
        """Checks to see if there are any unexpected sheets
        across a dataset.

        Args:
            data (ExcelLoaderData): data to be validated

        Returns:
            List[ValidationResult]: List of validation errors.
        """
        with self._validation() as response:
            results: list[ValidationResult] = []

            if data.unexpected_sheets:
                results.append(
                    ValidationResult(
                        message=self._(
                            "unexpected_sheets_validator.unexpected_sheets",
                            count=len(data.unexpected_sheets),
                        ),
                        severity=SeverityLevel.WARNING,
                        details={"unexpected_sheets": data.unexpected_sheets},
                    )
                )

            if data.hidden_sheets:
                results.append(
                    ValidationResult(
                        message=self._(
                            "unexpected_sheets_validator.hidden_sheets",
                            count=len(data.hidden_sheets),
                        ),
                        severity=SeverityLevel.ERROR,
                        details={"hidden_sheets": data.hidden_sheets},
                    )
                )

            response.details.extend(results)
        return response
