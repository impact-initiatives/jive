## Skip Logic Check

Some survey questions contain skip logic that determine when a question is shown or hidden.

Note: Cross-sheet column references are only supported when a child sheet references a column on a parent sheet.

**Implementation**: `common_validators/skip_logic_validator.py`

**Rule name:** `SkipLogicCheck`

**Check 1**

Checks if any survey questions that were hidden contain a response.

Returns an `error` if any values are found. 

**Check 2**

Checks if any survey questions that were shown due to skip logic do not contain a response if the question is marked as required.

Returns an `error` if any empty values are found. 

**Check 3**

Checks if any skip logic expressions cant be validated. This most likely occurs if:

- a reference column is in another sheet
- A survey column name was changed but the skip logic references to this column were not updated
- a function is not supported
- there are issues with the conversion of Kobo skip logic into Python code

Returns a `warning` if any expressions could not be converted. 