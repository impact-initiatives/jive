## Empty Column Value Check

Dataset schema columns have a property `allow_empty_values` which determines if a column is allowed to contain empty values.

Note: sheets classified as `raw_data_sheets` are exempt from this rule.

**Implementation**: `common_validators/empty_column_validator.py`

**Rule name:** `EmptyColumnCheck`

**Check 1**

Checks if there are any empty values in a column that has the `allow_empty_values` property set to False

Returns an `error` if any empty values are found. 