## Survey Choices Check

Many values in the datasets are picked from lists in the Kobo survey. These are reflected in the `survey` sheet through `select_one` or `select_multiple` questions and have corresponding choices in the `choices` sheet. 

`select_multiple` question responses are also exported as binary columns that reflect the individual choice options. For example, if the column `fruit`has the options `apple, mango` in the `choices` sheet then the data export will have the columns `fruit, fruit.apple, fruit.mango` with `fruit.apple, fruit.mango` containing values of `0`, `1`, or nothing depending on the survey response.

**Implementation**: `common_validators/survey_choices_validator.py`

**Rule name:** `SurveyChoicesCheck`

**Check 1**

Checks that `clean_data` values have a corresponding value in the `choices` sheet when they come from Kobo `select_one` or `select_multiple` questions.

Returns an `error` if any values are not found in the `choices` sheet.

**Check 2**

Checks that any questions listed on the `survey` sheet as a `select_one` or `select_multiple` has options listed on the  `choices` sheet

Returns an `error` if a question has no options on the `choices` sheet.

**Check 3**

Checks that the binary columns for a `select_multiple` question have valid values: `0`, `1`, or is empty (if there is no response in the parent column).

Returns an `error` if a binary column has an invalid value.

**Check 4**

Checks that the values in binary columns for a `select_multiple` reflect the value in the parent column. For example, if the `fruit` column contains `apple` then the value in the column `fruit.apple` should be `1`. This check works both directions.

Returns an `error` if there is a mismatch between a binary column and a parent column..