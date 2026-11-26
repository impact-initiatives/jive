## Raw Data vs Clean Data vs Cleaning Log Check

Any changes made between the `raw_data` and `clean_data` sheets should be reflected in the `cleaning_log` sheet.

Notes: 

- The precision of `decimal` and `datetime` value checks is reduced to allow more flexible comparisons.
- The questions/variables compared in this check do not include those in the `cleaning_log` with a `uuid` value of `'all'`.

**Implementation**: `common_validators/raw_clean_cleaning_log_validator.py`

**Rule name:** `RawToCleanToLogCheck`

**Check 1**

Checks the differences between the clean and raw data sheets and then checks that all the differences are reflected in the cleaning log.

Returns an `error` if differences are not reflected in the cleaning log.

Returns an `error` if there are differences and there is no cleaning log.