## Unique Column Check

Some columns listed in a dataset schema could be marked as unique - ie the column should contain only unique values. This is managed through the column property `is_unique`.

Note: sheets classified as `raw_data_sheets` are exempt from this rule.

**Implementation**: `common_validators/unique_column_validator.py`

**Rule name:** `UniqueColumnCheck`

**Check 1**

Checks to see if any expected unique columns contain any non unique values across relevant sheets.

Returns an `error` if any columns contain non-unique values