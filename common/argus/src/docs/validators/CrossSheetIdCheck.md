## Cross Sheet ID Check

This checks if ID values are found in linkable sheets.

**Implementation**: `common_validators/cross_sheet_id_check_validator.py`

**Rule name:** `CrossSheetIdCheck`

**Check 1**

Checks if IDs from a child or processed sheet (`clean_data`, `cleaning_log` etc) are not present in a parent or `raw_data` sheet when they should be there. For example. IDs from `clean_data` should be in `raw_data`. IDs from `cleaning_log` should be in `clean_data`. 

This check assumes the IDs should be found.

Returns an `error` if any IDs are not found.

**Check 2**

Checks if IDs from a child or processed sheet (`deletion_log` ) are present in another sheet (`cleaning_log`) when they should NOT be there. For example, IDs from `deletion_log` should NOT be in `cleaning_log`.  

This check assumes the IDs should not be found.

Returns an `error` if any IDs are found.