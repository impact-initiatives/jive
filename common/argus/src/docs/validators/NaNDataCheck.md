## NaN Value Check

Sometimes invalid numeric values like -999 are entered in surveys instead of a legitimate value.

Note: this check can return false positives as some values that are part of this check can be legitimate values for certain questions. Verify any records that are flagged as part of this check.

**Implementation**: `common_validators/nan_check_validator.py`

**Rule name:** `NaNDataCheck`

**Check 1**

Checks data across all loaded sheets for NaN values. Values being searched for are stored in `config.py`. 

Returns an `error` if any values are found.