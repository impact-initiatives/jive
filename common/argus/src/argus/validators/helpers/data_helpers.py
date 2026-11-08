import polars as pl

from argus.locales.il8n import _

from ...common.list_matching import get_set_overlap, match_sheet_columns, match_sheet_columns_ids
from ...common.schema_matching import get_matching_unique_columns
from ...config import settings
from ...loaders.base import DataColumnMap, DataSheetMap
from ...loaders.base_excel_loader import ExcelLoaderData
from ...models.base_dataset_schemas import BaseDatasetSchema
from ..base import SeverityLevel, ValidationResult
from .schema_helpers import consolidate_messages, get_schema_loaded_sheet


def get_data_loaded_sheet(
    data: ExcelLoaderData, sheet_name: str, rule: str, check_data: bool = True
) -> tuple[ValidationResult | None, DataSheetMap | None]:
    """Gets a data loaded sheet if it exists.

    Args:
        data (ExcelLoaderData): excel data
        sheet_name (str): name of sheet to load
        rule (str): validation rule
        check_data (bool): check to see if the dataframe actually contains data

    Returns:
        tuple[ValidationResult | None, SheetMap | None]: validation error if any,
             loaded sheet if found
    """
    result = None
    loaded_sheet = data.get_loaded_sheet(sheet_name=sheet_name)

    if loaded_sheet is None:
        result = ValidationResult(
            rule=rule,
            message=_("helpers.get_loaded_sheet", sheet=sheet_name, sheet_type="data"),
            severity=SeverityLevel.ERROR,
            sheet_name=sheet_name,
        )
    elif check_data:
        result = check_data_exists(loaded_sheet.data, sheet_name, rule)

    return result, loaded_sheet


def get_data_loaded_sheets(
    data: ExcelLoaderData, sheet_names: list[str], rule: str, check_data: bool = True
) -> tuple[ValidationResult | None, dict[str, DataSheetMap]]:
    """Gets a list of data loaded sheets if they exist.

    Args:
        data (ExcelLoaderData): excel data
        sheet_names (List[str]): list of sheet names to load
        rule (str): validation rule
        check_data (bool): check to see if the dataframe actually contains data

    Returns:
        tuple[List[ValidationResult], dict[str, SheetMap]]:  list of validation errors
             if any, dictionary of sheet names and loaded sheets if found
    """
    results: list[ValidationResult] = []
    loaded_sheets: dict[str, DataSheetMap] = {}

    for sheet in sheet_names:
        result, loaded_sheet = get_data_loaded_sheet(data, sheet, rule, check_data)

        if result is None:
            assert loaded_sheet is not None
            loaded_sheets[sheet] = loaded_sheet
        else:
            results.append(result)

    final_result = consolidate_messages(results, "sheets", "excel", rule)

    return final_result, loaded_sheets


def get_data_loaded_column(
    loaded_sheet: DataSheetMap, column_name: str, rule: str
) -> tuple[ValidationResult | None, DataColumnMap | None]:
    """Gets a data loaded column if found.

    Args:
        loaded_sheet (SheetMap): sheet the column is on
        column_name (str): name of the column to find
        rule (str): validation rule

    Returns:
        tuple[ValidationResult | None, ColumnMap | None]: validation error if any,
             loaded column if found
    """
    result = None

    column = loaded_sheet.get_column_map(column_name)
    if column is None:
        result = ValidationResult(
            rule=rule,
            message=_(
                "helpers.get_loaded_column",
                column=column_name,
                sheet=loaded_sheet.data_sheet_name,
                sheet_type="data",
            ),
            severity=SeverityLevel.ERROR,
            sheet_name=loaded_sheet.data_sheet_name,
            column_name=column_name,
        )

    return result, column


def get_data_loaded_columns(
    data: dict[str, DataSheetMap], rule: str
) -> tuple[ValidationResult | None, dict[str, DataColumnMap]]:
    """Gets a list of data loaded columns if found.

    Args:
        data (dict[str, SheetMap]): column names and data loaded sheet
        rule (str): validation rule

    Returns:
        tuple[List[ValidationResult], dict[str, ColumnMap]]: list of validation errors
             if any, column name and loaded column if found

    """
    results: list[ValidationResult] = []
    loaded_columns: dict[str, DataColumnMap] = {}

    for column, loaded_sheet in data.items():
        result, loaded_column = get_data_loaded_column(loaded_sheet, column, rule)

        if result is None:
            assert loaded_column is not None
            loaded_columns[column] = loaded_column
        else:
            results.append(result)

    final_result = consolidate_messages(results, "columns", "excel", rule)

    return final_result, loaded_columns


def get_data_sheet_id(
    sheet_name: str,
    schema: BaseDatasetSchema,
    loaded_sheet: DataSheetMap,
    rule: str,
    expected: int = 1,
) -> tuple[ValidationResult | None, list[DataColumnMap]]:
    """Gets unique columns for a scheema sheet and loaded sheet.

    Args:
        sheet_name (str): name of sheet
        schema (BaseDatasetSchema): dataset schema
        loaded_sheet (SheetMap):  loaded sheet
        rule (str): validation rule
        expected (int, optional): how many matches are expected. Defaults to 1.

    Returns:
        tuple[ValidationResult | None, List[ColumnMap]]: validation error if any,
             list of column matches if found
    """
    result = None
    ids = get_matching_unique_columns(schema, loaded_sheet, sheet_name)

    if not ids:
        result = ValidationResult(
            rule=rule,
            message=_("helpers.number_unique_columns", sheet=loaded_sheet.data_sheet_name, count=0),
            severity=SeverityLevel.ERROR,
            sheet_name=loaded_sheet.data_sheet_name,
        )
    elif len(ids) != expected:
        result = ValidationResult(
            rule=rule,
            message=_(
                "data_helpers.get_data_sheet_id.count_invalid",
                count=expected,
                sheet=sheet_name,
                excel_sheet=loaded_sheet.data_sheet_name,
            ),
            severity=SeverityLevel.ERROR,
            sheet_name=sheet_name,
        )
    return result, ids


def get_data_sheet_ids(
    schema: BaseDatasetSchema,
    data: dict[str, DataSheetMap],
    rule: str,
    expected: int = 1,
) -> tuple[list[ValidationResult], dict[str, list[DataColumnMap]]]:
    """Gets unique columns for a list of scheema sheets and loaded sheets.

    Args:
        schema (BaseDatasetSchema): dataset schema
        data (dict[str, SheetMap]): name of sheet, loaded sheet
        rule (str): validation rule
        expected (int, optional): how many matches are expected. Defaults to 1.

    Returns:
        tuple[List[ValidationResult], dict[str, List[ColumnMap]]]: _description_
    """
    results: list[ValidationResult] = []
    loaded_columns: dict[str, list[DataColumnMap]] = {}

    for sheet, loaded_sheet in data.items():
        result, loaded_column = get_data_sheet_id(sheet, schema, loaded_sheet, rule, expected)

        if result is None:
            assert loaded_column is not None
            loaded_columns[sheet] = loaded_column
        else:
            results.append(result)

    return results, loaded_columns


def get_matching_columns(
    source: list[DataColumnMap],
    source_sheet: str,
    target: list[DataColumnMap],
    target_sheet: str,
    rule: str,
) -> tuple[ValidationResult | None, list[tuple[DataColumnMap, DataColumnMap]]]:
    """Get matching id columns between sheets.

    Args:
        source (List[ColumnMap]): list of source columns
        source_sheet (str): source sheet
        target (List[ColumnMap]): list of target columns
        target_sheet (str): target sheet
        rule (str): validation rule

    Returns:
        tuple[ValidationResult | None, list[ColumnMap]]: validation errors if any,
            list of matched columns if found
    """

    result = None

    matching_columns: list[tuple[DataColumnMap, DataColumnMap]] = match_sheet_columns(
        source, target
    )
    # should only be one matching id column between the sheets.
    if len(matching_columns) != 1:
        result = ValidationResult(
            rule=rule,
            message=_(
                "data_helpers.get_matching_columns",
                source_sheet=source_sheet,
                target_sheet=target_sheet,
                count=len(matching_columns),
            ),
            severity=SeverityLevel.ERROR,
        )

    if result is None:
        assert matching_columns is not None

    return result, matching_columns


def get_matching_columns_alt(
    source: list[DataColumnMap],
    source_sheet: str,
    target: list[DataColumnMap],
    target_sheet: str,
    rule: str,
) -> tuple[ValidationResult | None, list[DataColumnMap], list[DataColumnMap]]:
    """Attempts to find two id like columns that could be used to try
        and link two sheets.

        Only is this if other more direct methods have been tried

    Args:
        source (List[ColumnMap]): list of source columns
        source_sheet (str): source sheet
        target (List[ColumnMap]): list of target columns
        target_sheet (str): target sheet
        rule (str): validation rule

    Returns:
        tuple[ValidationResult | None, list[DataColumnMap], list[DataColumnMap]]:
            validation results, matching id columns from source and target
    """
    result = None

    source_columns, target_columns = match_sheet_columns_ids(source, target)
    if len(source_columns) != 1 or len(target_columns) != 1:
        result = ValidationResult(
            rule=rule,
            message=_(
                "data_helpers.get_matching_columns_alt",
                source_sheet=source_sheet,
                target_sheet=target_sheet,
                source_count=len(source_columns),
                target_count=len(target_columns),
            ),
            severity=SeverityLevel.ERROR,
        )
    if result is None:
        assert source_columns is not None
        assert target_columns is not None

    return result, source_columns, target_columns


def get_id_linking_columns(
    schema: BaseDatasetSchema,
    data_loaded_sheets: dict[str, DataSheetMap],
    source_sheet: str,
    target_sheet: str,
    rule: str,
    min_overlap: float = settings.MIN_COLUMN_MATCHING_OVERLAP,
    exclude_id_values: list[str] | None = None,
) -> (
    tuple[list[ValidationResult], None, None]
    | tuple[list[ValidationResult], DataColumnMap, DataColumnMap]
):
    """Trys to find linkable id columns between two sheets.

    This follows the following process:
    - checks if the source sheet has a parent and if the target sheet
    is that parent.
        if so, use the parent id column from source
        and the id column from the target if found
    else
    - checks if both sheets have a unique column
       If they both have one then these columns are used
    - If only one or none of the sheets have a column from the above steps
        name matching is performed

    if possible linking columns are found then the intersection
    of their values is calculated. if there is a high enough
    intersection between their values then these colums are returned.
    else no columns are returned

    Note: if one sheet is likely to contain only a subset of the ids of
    the other sheet (cleaning log vs clean or clean vs raw) then the source
    sheet should always be the sheet that contains the subset of values.
    This is also the case when checking parent-child ids - the child sheet
    should be the source.

    Args:
        schema (BaseDatasetSchema): dataset schema
        data_loaded_sheets (dict[str, DataSheetMap]): the loaded data for the sheets
        source_sheet (str): name of the source sheet
        target_sheet (str): name of the target sheet
        rule (str): name of the rule calling this process
        min_overlap (float, optional): minimum overlap required to be considered linkable columns.
            Defaults to 0.9.
        exclude_id_values (list[str]): remove these items from the sets being compared. eg: 'all'
            from cleaning_log

    Returns:
        tuple[list[ValidationResult], None, None] |
            tuple[list[ValidationResult], DataColumnMap, DataColumnMap]: _description_
    """
    results: list[ValidationResult] = []
    exclude_id_values = [] if exclude_id_values is None else exclude_id_values

    result, child_schema_loaded_sheet = get_schema_loaded_sheet(schema, source_sheet, rule)
    if result is not None:
        results.append(result)
        return results, None, None
    assert child_schema_loaded_sheet is not None

    if (
        child_schema_loaded_sheet.parent_linking_column is not None
        and child_schema_loaded_sheet.parent_sheet == target_sheet
    ):
        # if checking parent-child links
        result_source, source_sheet_id_column = get_data_loaded_column(
            data_loaded_sheets[source_sheet], child_schema_loaded_sheet.parent_linking_column, rule
        )
        if result_source is not None:
            results.append(result_source)
            return results, None, None
        else:
            assert source_sheet_id_column is not None
            source_sheet_id_column = [source_sheet_id_column]
    else:
        # check if there is an id column
        result_source, source_sheet_id_column = get_data_sheet_id(
            schema=schema,
            sheet_name=source_sheet,
            loaded_sheet=data_loaded_sheets[source_sheet],
            rule=rule,
            expected=1,
        )

    result_target, target_sheet_id_column = get_data_sheet_id(
        schema=schema,
        sheet_name=target_sheet,
        loaded_sheet=data_loaded_sheets[target_sheet],
        rule=rule,
        expected=1,
    )

    if result_target is not None or result_source is not None:
        # if one of the sheets does not have a unique column then attempt
        # some exacpt name matching
        result_match, matching_columns = get_matching_columns(
            source=source_sheet_id_column
            if result_source is None
            else data_loaded_sheets[source_sheet].column_map,
            source_sheet=source_sheet,
            target=target_sheet_id_column
            if result_target is None
            else data_loaded_sheets[target_sheet].column_map,
            target_sheet=target_sheet,
            rule=rule,
        )
        if result_match is not None:
            # if no exact name match attempt some alternate name matches
            result_match_alt, source_sheet_id_column, target_sheet_id_column = (
                get_matching_columns_alt(
                    source=source_sheet_id_column
                    if result_source is None
                    else data_loaded_sheets[source_sheet].column_map,
                    source_sheet=source_sheet,
                    target=target_sheet_id_column
                    if result_target is None
                    else data_loaded_sheets[target_sheet].column_map,
                    target_sheet=target_sheet,
                    rule=rule,
                )
            )
            if result_match_alt is not None:
                results.append(
                    ValidationResult(
                        rule=rule,
                        message=_(
                            "data_helpers.get_id_linking_columns.no_columns",
                            source_sheet=source_sheet,
                            target_sheet=target_sheet,
                        ),
                        severity=SeverityLevel.ERROR,
                    )
                )
                return results, None, None
            else:
                source_sheet_id_column = source_sheet_id_column[0]
                target_sheet_id_column = target_sheet_id_column[0]
        else:
            source_sheet_id_column = matching_columns[0][0]
            target_sheet_id_column = matching_columns[0][1]

    else:
        source_sheet_id_column = source_sheet_id_column[0]
        target_sheet_id_column = target_sheet_id_column[0]

    # if a match was found check the overlap to make sure
    # that it is a legitimate match
    # Note: if a sheet is empty then this will return an error. If necessary,
    # an option to return a match if one sheet is empty could be added.
    result_overlap = check_id_column_overlap(
        source_column=source_sheet_id_column.data_column_name,
        source_sheet=source_sheet,
        target_column=target_sheet_id_column.data_column_name,
        target_sheet=target_sheet,
        data_loaded_sheets=data_loaded_sheets,
        rule=rule,
        min_overlap=min_overlap,
        exclude_id_values=exclude_id_values,
    )

    if result_overlap is not None:
        results.append(result_overlap)
        return results, None, None

    results.append(
        ValidationResult(
            rule=rule,
            message=_(
                "data_helpers.get_id_linking_columns.linked_columns",
                source_sheet=source_sheet,
                source_column=source_sheet_id_column.data_column_name,
                target_sheet=target_sheet,
                target_column=target_sheet_id_column.data_column_name,
            ),
            severity=SeverityLevel.INFO,
        )
    )

    return results, source_sheet_id_column, target_sheet_id_column


def check_id_column_overlap(
    source_column: str,
    source_sheet: str,
    target_column: str,
    target_sheet: str,
    data_loaded_sheets: dict[str, DataSheetMap],
    rule: str,
    min_overlap: float = settings.MIN_COLUMN_MATCHING_OVERLAP,
    exclude_id_values: list[str] | None = None,
) -> ValidationResult | None:
    """Compares the intersection of two columns and calculates their overlap.
    Useful for verifying that id columns that have been matched through their
    names are actually linkable.

    Note: if a sheet is empty then this will return an error. If necessary,
    an option to return a match if one sheet is empty could be added.

    Args:
        source_column (str): name of the source column
        source_data (DataFrame): dataframe of the source dataset
        source_sheet (str): name of the source sheet
        target_column (str): name of the target column
        target_dataframe (DataFrame): dataframe of the target dataset
        target_sheet (str): name of the target sheet
        rule (str): validation rule
        min_overlap (float, optional): minimum overlap required to be considered linkable columns.
            Defaults to 0.9.
        exclude_id_values (list[str]): remove these items from the sets being compared. eg: 'all'
            from cleaning_log

    Returns:
        ValidationResult | None: validation error if overlap is too low. otherwise None
    """
    exclude_id_values = [] if exclude_id_values is None else exclude_id_values
    result = None
    source_set = set(
        data_loaded_sheets[source_sheet]
        .data.select(pl.col(source_column).cast(pl.String))
        .to_series()
        .unique()
        .to_list()
    )
    source_set.difference_update(exclude_id_values)
    target_set = set(
        data_loaded_sheets[target_sheet]
        .data.select(pl.col(target_column).cast(pl.String))
        .to_series()
        .unique()
        .to_list()
    )
    target_set.difference_update(exclude_id_values)
    overlap = get_set_overlap(source_set, target_set)

    if overlap < min_overlap:
        result = ValidationResult(
            rule=rule,
            message=_(
                "data_helpers.check_id_column_overlap",
                source_sheet=source_sheet,
                source_column=source_column,
                target_sheet=target_sheet,
                target_column=target_column,
                overlap=overlap,
                min_overlap=min_overlap,
            ),
            severity=SeverityLevel.ERROR,
        )

    return result


def check_data_exists(data: pl.DataFrame, sheet: str, rule: str) -> ValidationResult | None:
    """Checks that a dataframe has data. If no data is found an error is returned.

    Args:
        data (pl.DataFrame): Dataframe to check
        sheet (str): Name of excel sheet
        rule (str): validation Rule

    Returns:
        ValidationResult | None: error if no data in dataframe, else None
    """
    if data.height < 1:
        return ValidationResult(
            rule=rule,
            message=_(
                "data_helpers.check_data_exists",
                sheet=sheet,
            ),
            severity=SeverityLevel.ERROR,
        )
