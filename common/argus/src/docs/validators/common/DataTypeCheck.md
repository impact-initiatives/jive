## Datatype Check

Kobo surveys can specify a data type for responses (numeric, date etc). The data in the dataset should be the same type. 

Note: this check currently treats excel numeric dates (eg: 46187.0) as invalid.

**Implementation**: `common_validators/column_data_type_validator.py`

**Rule name:** `DataTypeCheck`

**Check 1**

Checks if values for questions listed as numeric (int, decimal) are all numeric

Returns an `error` if any non-numeric values are found

**Check 2**

Checks if values for questions listed as temporal (date) are all temporal.

Returns an `error` if any non-temporal values are found