## Cross Sheet Row Sum Check

All rows removed from a dataset should be accounted for. 

**Implementation**: `common_validators/cross_sheet_row_sum_check_validator.py`

**Rule name:** `CrossSheetRowSumCheck`

**Check 1**

Checks if the number of records in `raw_data` equals the sum of the records from `clean_data` and `deletion_log`. In the case of loops when the child sheet does not have its own `deletion_log`, a `deletion_log` record could represent deleting multiple child records so the `deletion_log`record is linked to the child’s parent to get an accurate count of the deleted child records. 

Returns an `error` if there is a difference. 