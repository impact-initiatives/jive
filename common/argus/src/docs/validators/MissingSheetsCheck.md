## Missing Sheets Check

Checks to see if any expected sheets are missing across a dataset. Expected sheets are those specified in the dataset schema, for example `clean_data`.

**Implementation**: `common_validators/missing_sheets_validator.py`

**Rule name:** `MissingSheetsCheck`

**Check 1**

Checks if any sheets listed as required were not found in the dataset.

Returns an `error` if any sheets are missing.

**Check 2**

Checks if any sheets listed as optional were not found in the dataset.

Returns a `warning` if any sheets are missing.