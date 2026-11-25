## Cleaning Log vs Clean Data Check

All changes listed in a `cleaning_log` should be reflected in the `clean_data` sheet.

Note: 

- The precision of `decimal` and `datetime` value checks is reduced to allow more flexible comparisons.
- Any records in the `cleaning_log` with a `uuid` value of `'all'` are removed from this check.

**Implementation**: `common_validators/cleaning_log_to_clean_validator.py`

**Rule name:** `CleaningLogToCleanCheck`

**Check 1**

Checks if survey responses listed in `cleaning_log` have multiple updates for the same question.

Returns a `warning` for records that have multiple updates. These records are removed from subsequent checks.

**Check 2**

Checks if changes listed in the `cleaning_log` have the same value listed under the `old_value` and `new_value` columns.

Returns a `warning` for any records that have the same old and new value. 

**Check 3**

Checks if questions listed in the `cleaning_log` are not present in the `clean_data` sheet.

Returns a `warning` for any questions not in `clean_data` and removes these questions from subsequent checks. 

**Check 4**

Checks if changes listed in the `cleaning_log` are not reflected in the `clean_data` sheet.

Returns an `error` for any `cleaning_log` changes not reflected in `clean_data`.

**Check 5**

Checks if no values were recorded as a change in the `cleaning_log`. This is based on the values in the `change_type` column. If no changes are found it is likely that the incorrect values are being used in this column.

Returns an `error` if no changes are found in the `cleaning_log`.