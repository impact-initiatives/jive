## Consent Check

All survey responses in the dataset should have provided consent for their data to be collected and used.

**Implementation**: `common_validators/consent_check_validator.py`

**Rule name:** `ConsentCheck`

**Check 1**

Checks that any records in `raw_data` that did not provide consent are not present in `clean_data`.

Returns an `error` if any records were found.