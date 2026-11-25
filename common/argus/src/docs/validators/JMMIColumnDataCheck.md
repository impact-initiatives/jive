## JMMI Column Data Checks

Certain columns are expected to have data structured in a certain way. Note: this rule does not check for empty values - this should be managed using the `EmptyColumnCheck`.

**Implementation**: `jmmi/column_data_validator.py`

**Rule name:** `JMMIColumnDataCheck`

**Check 1 (D004)**

The `country` column in the `clean_data`, `meb_analysis` and `mfs_analysis` sheets should only contain 3 uppercase letters

Returns an `error` if any infringing column values were found.

**Check 1 (D005)**

The `round` column in the `clean_data` sheet should start with `country`, contain
`month` and end with `year`.

Returns an `error` if any infringing column values were found.