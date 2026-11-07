import re
from dataclasses import dataclass
from pathlib import Path, PosixPath
from typing import override

import polars as pl

from ...common.list_matching import lower_list_items, match_list, upper_list_items
from ...loaders.base_excel_loader import ExcelLoaderData
from ...utils.yaml_loader import load_file
from ...validators.base import BaseValidator, SeverityLevel, ValidationResult
from ..helpers.data_helpers import (
    get_data_loaded_sheets,
)


@dataclass(slots=True)
class ColumnParts:
    country_code: str | None = None
    suffix: str | None = None
    post_suffix: str | None = None
    remaining_text: str | None = None
    column_variable_prefix: str | None = None
    column_type: str | None = None
    column_variable: str | None = None


class JMMIColumnNameCheck(BaseValidator):
    def __init__(
        self,
        clean_data_sheet: str = "clean_data",
        raw_data_sheet: str = "raw_data",
        country_column: str = "country",
    ):
        self.clean_data_sheet: str = clean_data_sheet
        self.raw_data_sheet: str = raw_data_sheet
        self.country_column: str = country_column

    @property
    @override
    def name(self) -> str:
        return "JMMIColumnNameCheck"

    def _load_file(self, file_path: Path, file_name: str):

        file = file_path / file_name
        file_list = load_file(file)[0][file.stem]
        return lower_list_items(file_list)

    @override
    def validate(
        self, data: ExcelLoaderData, **kwargs: str | int | float | Path
    ) -> list[ValidationResult]:
        """Validates column names for jmmi datasets.

        JMMI datasets have standardised naming conventions.

        This process attempts to spit a column into its respective parts. Eg:

        bean_wholesale_stock_duration_days_item
        item: bean_wholesale > column_variable_prefix
        column name: stock_duration_days_item > column_variable

        SSD_groundnut_stock_duration_unit_so
        prefix: SSD > country_code
        suffix: so > suffix
        item: bean_wholesale > column_variable_prefix
        column name: stock_duration_days_item > column_variable

        shop_availability_item.maize_grain
        column name: shop_availability_item > column_variable
        item: maize_grain > post_suffix > column_variable_prefix

        Using these parts the follwoing rules are checked:
        - country specific variables  have an appropriate prefix (country_code)
        - country specific variables have an appropriate suffix (suffix)
        - items should be in the goods dictionary (column_variable_prefix)
        - non country specific variables should be in the column name dictionary (column_variable)
        - country specific variables are not standardisable
            (column_variable_prefix + column_variable)

        All of these checks assume the word "item" is in the column name.

        also checking:
        - certain columns are removed from the dataset (columns_to_remove)

        Args:
            data (ExcelLoaderData): data (ExcelLoaderData): data to be validated

        Returns:
            list[ValidationResult]: a list of validation results
        """

        results: list[ValidationResult] = []
        column_parts: dict[str, ColumnParts] = {}
        items_found: set[str] = set()
        # B004
        items_not_in_dictionary: list[dict[str, str]] = []
        # B004 addition
        variables_not_in_dictionary: list[dict[str, str]] = []
        # B001, B002
        missing_prefix_or_suffix: list[dict[str, str]] = []
        # B003
        standardisable_country_columns: list[dict[str, str]] = []
        pattern = r"^([a-zA-Z0-9_]+)(?:[^a-zA-Z0-9_]+(.+))?$"
        # E001
        invalid_columns: list[dict[str, str]] = []
        columns_to_remove: list[str] = [
            "_index",
            "version",
            "deviceid",
            "trader_name",
            "shop_name",
            "organization_name",
            "organization",
            "organization_name_label",
            "enumerator",
            "submission_time",
            "submitted_by",
        ]

        dataset_config_directory = kwargs["dataset_config_directory"]
        assert type(dataset_config_directory) is PosixPath

        jmmi_config: Path = dataset_config_directory / "jmmi" / "config"

        # config files stored in argus_schemas repoistory
        country_codes_list: list[str] = self._load_file(jmmi_config, "iso_codes.yaml")
        suffix_list: list[str] = self._load_file(jmmi_config, "suffix_list.yaml")
        items_dictionary: list[str] = self._load_file(jmmi_config, "items.yaml")
        item_variables: list[str] = self._load_file(jmmi_config, "item_variables.yaml")
        currency_codes: list[str] = self._load_file(jmmi_config, "currency_codes.yaml")

        country_codes_list = upper_list_items(country_codes_list)

        result, data_loaded_sheets = get_data_loaded_sheets(
            data=data,
            sheet_names=[self.clean_data_sheet, self.raw_data_sheet],
            rule=self.name,
        )

        if result is not None:
            results.append(result)
            return results

        clean_data_sheet_columns = data_loaded_sheets[self.clean_data_sheet].original_column_names

        for column in clean_data_sheet_columns:
            parts = ColumnParts()

            # some values have other separators after the final _
            # eg: SSD_grinding_costs_item_sm.sorghum
            # so split it out to get the main part
            post_suffix_match = re.match(pattern, column)
            if post_suffix_match is not None:
                parts.remaining_text = post_suffix_match.group(1)
                parts.post_suffix = post_suffix_match.group(2)

                assert parts.remaining_text is not None
            else:
                parts.remaining_text = column

            # check for country code prefix
            splits = parts.remaining_text.split("_")
            if splits[0] in country_codes_list:
                parts.country_code = splits[0]
                parts.remaining_text = parts.remaining_text.replace(splits[0] + "_", "", 1)

            # check for suffix
            suffix_match = re.match(r"[a-zA-Z0-9]*", splits[-1])
            if suffix_match is not None:
                final_split = suffix_match.group()
                if final_split in suffix_list:
                    parts.suffix = final_split
                    parts.remaining_text = "".join(
                        parts.remaining_text.rsplit("_" + final_split, 1)[0]
                    )

            # country specific columns missing either a prefix or suffix
            if (parts.country_code and not parts.suffix) or (
                not parts.country_code and parts.suffix
            ):
                missing_prefix_or_suffix.append(
                    {
                        "sheet": self.clean_data_sheet,
                        "column": column,
                        "value": f"prefix: {parts.country_code}, suffix: {parts.suffix}",
                        "issue": self._(
                            "jmmi_column_name_validator.missing_prefix_or_suffix.issue"
                        ),
                    }
                )

            # get item columns and item types
            if "item" in parts.remaining_text:
                parts.column_type = "item"

                # get variable (availability_in_3_months_item etc) and
                # remove it from the remaining text
                variable_matches = [
                    variable for variable in item_variables if variable in parts.remaining_text
                ]
                if variable_matches:
                    parts.column_variable = max(variable_matches, key=len)
                    parts.remaining_text = parts.remaining_text.replace(
                        "_" + parts.column_variable, ""
                    )

                # check if item is in dictionary
                item_matches = [item for item in items_dictionary if item in parts.remaining_text]
                if item_matches:
                    # if multiple matches get the longest
                    # ie we might find bread_subsidised and bread.
                    # the longest match is the one we want
                    parts.column_variable_prefix = max(item_matches, key=len)
                    parts.remaining_text = parts.remaining_text.replace(
                        parts.column_variable_prefix + "_", ""
                    )
                elif parts.post_suffix:
                    # this tends to store the item as well
                    if parts.post_suffix in items_dictionary:
                        parts.column_variable_prefix = parts.post_suffix

                    elif (
                        parts.post_suffix not in country_codes_list
                        and parts.post_suffix not in currency_codes
                    ):
                        # sometimes the country code is repeated or there is a currency code
                        # unknown item
                        items_not_in_dictionary.append(
                            {
                                "sheet": self.clean_data_sheet,
                                "column": column,
                                "value": parts.post_suffix,
                                "issue": self._(
                                    "jmmi_column_name_validator.items_not_in_dictionary.issue"
                                ),
                            }
                        )
                    parts.remaining_text = parts.remaining_text.replace(parts.post_suffix + "_", "")

                # item variable not in list?
                if (
                    "item" in parts.remaining_text
                    and parts.country_code is None
                    and parts.suffix is None
                ):
                    # means there is probably an incorrect variable
                    variables_not_in_dictionary.append(
                        {
                            "sheet": self.clean_data_sheet,
                            "column": column,
                            "value": parts.remaining_text,
                            "issue": self._(
                                "jmmi_column_name_validator.variables_not_in_dictionary.issue"
                            ),
                        }
                    )

                if parts.column_variable_prefix is None and parts.post_suffix is None:
                    # unknown item
                    items_not_in_dictionary.append(
                        {
                            "sheet": self.clean_data_sheet,
                            "column": column,
                            "value": parts.remaining_text,
                            "issue": self._(
                                "jmmi_column_name_validator.items_not_in_dictionary.issue"
                            ),
                        }
                    )

                if (
                    parts.column_variable_prefix is not None
                    and parts.column_variable is not None
                    and (parts.country_code is not None or parts.suffix is not None)
                ):
                    # items that are country variables but have items and column names that have
                    # been standardised
                    standardisable_country_columns.append(
                        {
                            "sheet": self.clean_data_sheet,
                            "column": column,
                            "value": f"standardised column: {parts.column_variable_prefix + '_'}"
                            + f"{parts.column_variable}",
                            "issue": self._(
                                "jmmi_column_name_validator.standardisable_columns.issue"
                            ),
                        }
                    )

                if parts.column_variable_prefix:
                    # store all items found for later use
                    items_found.add(parts.column_variable_prefix)

            column_parts[column] = parts

        invalid_columns_clean_data = match_list(columns_to_remove, clean_data_sheet_columns)
        invalid_columns_raw_data = match_list(
            columns_to_remove, data_loaded_sheets[self.raw_data_sheet].data.columns
        )

        for column in invalid_columns_clean_data:
            invalid_columns.append(
                {
                    "sheet": self.clean_data_sheet,
                    "column": column,
                    "value": "",
                    "issue": self._("jmmi_column_name_validator.invalid_columns.issue"),
                }
            )
        for column in invalid_columns_raw_data:
            invalid_columns.append(
                {
                    "sheet": self.raw_data_sheet,
                    "column": column,
                    "value": "",
                    "issue": self._("jmmi_column_name_validator.invalid_columns.issue"),
                }
            )

        if items_not_in_dictionary:
            items_not_in_dictionary_df = pl.DataFrame(items_not_in_dictionary)
            results.append(
                ValidationResult(
                    rule=self.name,
                    message=self._(
                        "jmmi_column_name_validator.items_not_in_dictionary",
                        count=items_not_in_dictionary_df.height,
                    ),
                    severity=SeverityLevel.ERROR,
                    details=items_not_in_dictionary_df.to_dict(as_series=False),
                )
            )

        if missing_prefix_or_suffix:
            missing_prefix_or_suffix_df = pl.DataFrame(missing_prefix_or_suffix)
            results.append(
                ValidationResult(
                    rule=self.name,
                    message=self._(
                        "jmmi_column_name_validator.missing_prefix_or_suffix",
                        count=missing_prefix_or_suffix_df.height,
                    ),
                    severity=SeverityLevel.ERROR,
                    details=missing_prefix_or_suffix_df.to_dict(as_series=False),
                )
            )

        if variables_not_in_dictionary:
            variables_not_in_dictionary_df = pl.DataFrame(variables_not_in_dictionary)

            results.append(
                ValidationResult(
                    rule=self.name,
                    message=self._(
                        "jmmi_column_name_validator.variables_not_in_dictionary",
                        count=variables_not_in_dictionary_df.height,
                    ),
                    severity=SeverityLevel.ERROR,
                    details=variables_not_in_dictionary_df.to_dict(as_series=False),
                )
            )

        if standardisable_country_columns:
            standardisable_country_columns_df = pl.DataFrame(standardisable_country_columns)

            results.append(
                ValidationResult(
                    rule=self.name,
                    message=self._(
                        "jmmi_column_name_validator.standardisable_columns",
                        count=standardisable_country_columns_df.height,
                    ),
                    severity=SeverityLevel.ERROR,
                    details=standardisable_country_columns_df.to_dict(as_series=False),
                )
            )

        if invalid_columns:
            invalid_columns_df = pl.DataFrame(invalid_columns)

            results.append(
                ValidationResult(
                    rule=self.name,
                    message=self._(
                        "jmmi_column_name_validator.invalid_columns",
                        count=invalid_columns_df.height,
                    ),
                    severity=SeverityLevel.ERROR,
                    details=invalid_columns_df.to_dict(as_series=False),
                )
            )

        return results
