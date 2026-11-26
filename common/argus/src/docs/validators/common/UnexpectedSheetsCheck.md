## Unexpected Sheets Check

Unexpected sheets are sheets that are found in a dataset but not matched or found in the dataset schema. 

**Implementation**: `common_validators/unexpected_sheets_validator.py`

**Rule name:** `UnexpectedSheetsCheck`

**Check 1**

Checks to see if there are any unexpected sheets present in the excel dataset. 

Returns a `warning` if any are found.

**Check 2**

Checks if there are any hidden sheets in the excel dataset. 

Returns an `error` if any are found.