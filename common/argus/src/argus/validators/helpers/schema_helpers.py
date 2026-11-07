from argus.locales.il8n import _

from ...models.base import ProcessValueMap, SchemaColumnMap, SchemaSheetMap
from ...models.base_dataset_schemas import BaseDatasetSchema
from ..base import SeverityLevel, ValidationResult


def get_schema_process_value(
    process_value_map_name: str,
    sheet_name: str,
    schema_column: SchemaColumnMap,
    rule: str,
) -> tuple[ValidationResult | None, ProcessValueMap | None]:
    """Gets schema process values if found

    Args:
        process_value_map_name (str): name of process
        sheet_name (str): sheet name
        schema_column (ColumnMapping): schema column that process is linked to
        rule (str): validation rule

    Returns:
        tuple[ValidationResult | None, ProcessValueMap | None]: validation errors if any
            , process values if found
    """

    result = None

    process_values = schema_column.get_process_values(process_value_map_name)

    if process_values is None or len(process_values.values) == 0:
        result = ValidationResult(
            rule=rule,
            message=_(
                "schema_helpers.get_schema_process_value",
                column=schema_column.standard_name,
                process=process_value_map_name,
            ),
            severity=SeverityLevel.ERROR,
            sheet_name=sheet_name,
            column_name=schema_column.standard_name,
        )
    else:
        assert process_values is not None

    return result, process_values


def get_schema_process_values(
    data: dict[str, dict[str, SchemaColumnMap]], rule: str
) -> tuple[list[ValidationResult], dict[str, ProcessValueMap]]:
    """Gets a list of schema process values if found.


    Args:
        data (dict[str, dict[str, ColumnMapping]]): sheet name,
             [process value name, schema column]
        rule (str): validation rule

    Returns:
        tuple[List[ValidationResult], dict[str, ProcessValueMap]]: validation errors if
             any, process value name, process values if found
    """
    results: list[ValidationResult] = []
    process_values: dict[str, ProcessValueMap] = {}

    for sheet, item in data.items():
        for process, column in item.items():
            result, process_value = get_schema_process_value(process, sheet, column, rule)

            if result is None:
                assert process_value is not None
                process_values[process] = process_value
            else:
                results.append(result)

    return results, process_values


def get_schema_loaded_column(
    loaded_sheet: SchemaSheetMap, column: str, rule: str
) -> tuple[ValidationResult | None, SchemaColumnMap | None]:
    """Gets a schema column if it exists.

    Args:
        loaded_sheet (SheetMapping): loaded schema sheet containing the column
        column (str): column to find
        rule (str): validation rule

    Returns:
        tuple[ValidationResult | None, ColumnMapping | None]: validation errors if any,
          loaded column
    """
    result = None

    schema_column = loaded_sheet.get_column(column)

    if schema_column is None:
        # should not actually happen as its already mapped above.
        result = ValidationResult(
            rule=rule,
            message=_(
                "helpers.get_loaded_column",
                column=column,
                sheet=loaded_sheet.standard_name,
                sheet_type="schema",
            ),
            severity=SeverityLevel.ERROR,
            sheet_name=loaded_sheet.standard_name,
            column_name=column,
        )
    return result, schema_column


def get_schema_loaded_columns(
    data: dict[str, SchemaSheetMap], rule: str
) -> tuple[ValidationResult | None, dict[str, SchemaColumnMap]]:
    """Gets a list of schema columns if they exists

    Args:
        data (dict[str, SheetMapping]): column name, loaded schema sheet
        rule (str): validation rule

    Returns:
        tuple[List[ValidationResult], dict[str, ColumnMapping]]: list of validation
             errors if any, column and schema column map
    """

    results: list[ValidationResult] = []
    loaded_columns: dict[str, SchemaColumnMap] = {}

    for column, sheet in data.items():
        result, schema_column = get_schema_loaded_column(sheet, column, rule)
        if result is None:
            assert schema_column is not None
            loaded_columns[column] = schema_column
        else:
            results.append(result)

    final_result = consolidate_messages(results, "columns", "schema", rule)

    return final_result, loaded_columns


def get_schema_loaded_sheet(
    schema: BaseDatasetSchema, sheet_name: str, rule: str
) -> tuple[ValidationResult | None, SchemaSheetMap | None]:
    """Gets a schema loaded sheet if it exists.

    Args:
        schema (BaseDatasetSchema): dataset scheema
        sheet_name (str): name of sheet to load
        rule (str): validation rule

    Returns:
        tuple[ValidationResult | None, SheetMapping | None]: validation error if any,
             loaded sheet if found
    """
    result = None
    schema_sheet = schema.get_schema_loaded_sheet(sheet_name=sheet_name)

    if not schema_sheet:
        result = ValidationResult(
            rule=rule,
            message=_("helpers.get_loaded_sheet", sheet=sheet_name, sheet_type="schema"),
            severity=SeverityLevel.ERROR,
            sheet_name=sheet_name,
        )

    return result, schema_sheet


def get_schema_loaded_sheets(
    schema: BaseDatasetSchema, sheet_names: list[str], rule: str
) -> tuple[ValidationResult | None, dict[str, SchemaSheetMap]]:
    """Gets a list of schema loaded sheets if it exists.

    Args:
        schema (BaseDatasetSchema): dataset scheema
        sheet_names (List[str]): list of names of sheets to load
        rule (str): validation rule

    Returns:
        tuple[List[ValidationResult], dict[str, SheetMapping]]: list of validation
             errors if any,  dictionary of sheet names and loaded sheets if found
    """
    results: list[ValidationResult] = []
    loaded_sheets: dict[str, SchemaSheetMap] = {}

    for sheet in sheet_names:
        result, loaded_sheet = get_schema_loaded_sheet(schema, sheet, rule)

        if result is None:
            assert loaded_sheet is not None
            loaded_sheets[sheet] = loaded_sheet
        else:
            results.append(result)

    final_result = consolidate_messages(results, "sheets", "schema", rule)

    return final_result, loaded_sheets


def consolidate_messages(
    results: list[ValidationResult], item_type: str, item_source: str, rule: str
) -> ValidationResult | None:
    """Consolidates messages. Useful when the messages are the same except for
    different sheets or columns. eg: get_schema_loaded_sheets

    Args:
        results (list[ValidationResult]): list of validation results
        item_type (str): type of item being consolidated. 'sheets' or 'columns'
        item_source (str): source of item being consolidated. 'schema' or 'excel'
        rule (str): calling validation rule

    Returns:
        ValidationResult | None: returns a consolidated result or None if no results
    """
    items: list[str] = []
    # column_items: dict[str, list[str]] = {}

    if len(results) > 1:
        for result in results:
            if result.column_name is not None and item_type == "columns":
                items.append(result.column_name)
                # if result.sheet_name is not None:
                #     if result.sheet_name in column_items:
                #         column_items[result.sheet_name].append(result.column_name)
                #     else:
                #         column_items[result.sheet_name] = [result.column_name]

            if result.sheet_name is not None and item_type == "sheets":
                items.append(result.sheet_name)

        result = ValidationResult(
            rule=rule,
            message=_(
                "schema_helpers.missing_items",
                item_type=item_type,
                item_source=item_source,
                count=len(items),
            ),
            severity=SeverityLevel.ERROR,
            details={f"missing_{item_type}": items},  # if item_type == "sheets" else column_items},
        )
        return result
    elif len(results) == 1:
        return results[0]
    else:
        return None
