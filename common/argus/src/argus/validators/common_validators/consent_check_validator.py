from typing import override

import polars as pl

from ...loaders.base_excel_loader import ExcelLoaderData
from ...models.base_dataset_schemas import BaseDatasetSchema
from ..base import BaseValidator, SeverityLevel, ValidationResult
from ..helpers.data_helpers import (
    get_data_loaded_columns,
    get_data_loaded_sheets,
    get_data_sheet_ids,
)
from ..helpers.schema_helpers import (
    get_schema_loaded_column,
    get_schema_loaded_sheets,
    get_schema_process_value,
)


class ConsentCheck(BaseValidator):
    """Checks that records in raw_data that did not provide consent are
    not present in clean_data"""

    def __init__(
        self,
        schema: BaseDatasetSchema,
        raw_data_sheet: str = "raw_data",
        clean_data_sheet: str = "clean_data",
        schema_consent_column: str = "consent",
    ) -> None:
        """
        Args:
            schema (BaseDatasetSchema): dataset schema
            raw_data_sheet (str, optional): schema raw_data sheet name.
                Defaults to 'raw_data'.
            clean_data_sheet (str, optional): shema clean_data sheet name.
                Defaults to 'clean_data'.
            schema_consent_column (str, optional): column in raw_data that gives
                consent value. Defaults to 'consent'.
        """
        self.raw_data_sheet: str = raw_data_sheet
        self.clean_data_sheet: str = clean_data_sheet
        self.schema: BaseDatasetSchema = schema
        self.schema_consent_column: str = schema_consent_column
        self.process_value_map_name: str = "consent_check_validation"

    @property
    @override
    def name(self) -> str:
        return "ConsentCheck"

    @override
    def validate(
        self, data: ExcelLoaderData, **kwargs: str | int | float
    ) -> list[ValidationResult]:
        """Checks that records in raw_data that did not provide consent are
        not present in clean_data.

        Args:
            data (ExcelLoaderData): data to be validated

        Returns:
            List[ValidationResult]: List of validation errors.
        """
        results: list[ValidationResult] = []

        result, data_loaded_sheets = get_data_loaded_sheets(
            data=data,
            sheet_names=[self.clean_data_sheet, self.raw_data_sheet],
            rule=self.name,
        )

        if result is not None:
            results.append(result)
            return results

        result, data_loaded_columns = get_data_loaded_columns(
            data={self.schema_consent_column: data_loaded_sheets[self.raw_data_sheet]},
            rule=self.name,
        )

        if result is not None:
            results.append(result)
            return results

        result, schema_loaded_sheets = get_schema_loaded_sheets(
            schema=self.schema, sheet_names=[self.raw_data_sheet], rule=self.name
        )

        if result is not None:
            results.append(result)
            return results

        result, schema_consent_column = get_schema_loaded_column(
            schema_loaded_sheets[self.raw_data_sheet],
            data_loaded_columns[self.schema_consent_column].schema_column_name,
            self.name,
        )
        if result is not None:
            results.append(result)
            return results

        assert schema_consent_column is not None

        result, consent_values = get_schema_process_value(
            self.process_value_map_name,
            self.raw_data_sheet,
            schema_consent_column,
            self.name,
        )
        if result is not None:
            results.append(result)
            return results

        assert consent_values is not None

        result, data_sheet_ids = get_data_sheet_ids(
            schema=self.schema,
            data={
                self.clean_data_sheet: data_loaded_sheets[self.clean_data_sheet],
                self.raw_data_sheet: data_loaded_sheets[self.raw_data_sheet],
            },
            rule=self.name,
        )

        if result:
            results.extend(result)
            return results

        raw_data_id_column = data_sheet_ids[self.raw_data_sheet][0]
        clean_data_id_column = data_sheet_ids[self.clean_data_sheet][0]

        # get records that have not provided consent
        raw_data_filter_df = (
            data_loaded_sheets[self.raw_data_sheet]
            .data.filter(
                ~pl.col(data_loaded_columns[self.schema_consent_column].data_column_name)
                .str.to_lowercase()
                .is_in(consent_values.values)
            )
            .select(
                [
                    raw_data_id_column.data_column_name,
                    data_loaded_columns[self.schema_consent_column].data_column_name,
                ]
            )
        )

        if raw_data_filter_df.height > 0:
            # join to clean_data to see if clean_data contains any of the records
            clean_data_filter_df = data_loaded_sheets[self.clean_data_sheet].data.join(
                other=raw_data_filter_df,
                left_on=clean_data_id_column.data_column_name,
                right_on=raw_data_id_column.data_column_name,
                how="inner",
            )
            if clean_data_filter_df.height > 0:
                results.append(
                    ValidationResult(
                        rule=self.name,
                        message=self._(
                            "consent_check_validator.consent_check",
                            count=clean_data_filter_df.height,
                            sheet=data_loaded_sheets[self.clean_data_sheet].data_sheet_name,
                        ),
                        severity=SeverityLevel.ERROR,
                        details=clean_data_filter_df.select(
                            [clean_data_id_column.data_column_name]
                        ).to_dict(as_series=False),
                    )
                )

        return results
