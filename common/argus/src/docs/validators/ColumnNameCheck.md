## Column Name Check

When exporting data from Kobo, column names should be variables instead of labels.  

Note: Kobo `survey` and `choices` sheets are not included in this check.

**Implementation**: `common_validators/column_name_validator.py`

**Rule name:** `ColumnNameCheck`

**Check 1**

Check column names are variables instead of labels. This is performed through regex matching that checks that the column name only contains certain characters. 

Returns an `error` if any matches are found