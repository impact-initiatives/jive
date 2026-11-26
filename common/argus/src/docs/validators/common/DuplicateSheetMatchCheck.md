## Duplicate Sheets Check

Dataset schema sheets should only match to one excel sheet. Multiple matches could occur if fuzzy matching is being used.

If a schema sheet includes a `matching_term` then it is possible that it could be matched to multiple excel files. This is expected behaviour so these matches are not included in this rule. For example, `analysis` submissions expect an `analysis_table` sheet but there could be multiple analysis sheets so these matches are done based on having the term `analysis` in the sheet name. All matched excel_sheets are matched to the one schema sheet. 

**Implementation**: `common_validators/duplicate_sheet_match_validator.py`

**Rule name:** `DuplicateSheetMatchCheck`

**Check 1**

Checks to see if a dataset schema sheet was matched to multiple excel sheets.

Returns an `error` if a sheet was matched multiple times.