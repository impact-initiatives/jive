## Mandatory Columns Check

Expected columns are specified in the dataset schema. For example, `uuid` in `clean_data`. Columns can be either required or optional. This is managed through the column property `required`.

**Implementation**: `common_validators/mandatory_column_validator.py`

**Rule name:** `MandatoryColumnsCheck`

**Check 1**

Checks if any required columns listed as part of a dataset schema were not found.

Returns an `error` if any columns were not found in the dataset.

**Check 2**

Checks if any optional columns listed as part of a dataset schema were not found.

Returns a `warning` if any columns were not found.