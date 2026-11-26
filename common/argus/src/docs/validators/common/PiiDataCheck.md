## PII Data Check

PII data should not be included in a published/archived dataset. Checks all the sheets for possible PII Data. 

**Implementation**: `common_validators/pii_validator.py`

**Rule name:** `PiiDataCheck`

**Check 1**

Checks the column names to see if the name suggests if it contains PII data.. `validators/options.py` stores a list of common PII column names. Column names are compared to this list with fuzzy matching also performed.

Returns a `warning` if any possible PII columns are found.

**Check 2**

Checks the data in the sheets for possible PII data using Regex. This is currently limited to checking for email addresses and phone numbers. The phone number check is quite basic/limited. It looks for numbers that start with a 0 or +, are not decimals and are at least 6 digits long.

Returns a `warning` if any possible PII data is found.