## JMMI Meb Analysis Checks

JMMI meb analysis columns have [naming standards](https://acted.sharepoint.com/:x:/r/sites/IMPACT-Public_Services_Markets_Infrastructure/Shared%20Documents/Cash%20and%20Markets/Toolbox/Internal%20resources/1.%20Toolkits%20and%20guidance/JMMI/6.%20Data%20standardization%20guidelines/JMMI%20Minimum%20Data%20Standards/02_DICTIONARY_2024_JMMI_minimum_data_standards.xlsx?d=w3b0c300fc9c244c2b6bd0ed556f23e29&csf=1&web=1&e=UhA7Jv). These checks validate the column names in the meb_analysis sheet against the naming standards.

**Implementation**: `jmmi/meb_analysis_validator.py`

**Rule name:** `JMMIMebAnalysisCheck`

**Check 1 (C001)**

Checks there are at least two columns ending in "_local_currency" and at lease two columns ending in "usd_xrate_official”

Returns an `error` if any not enough columns were found.

**Check 2 (C005)**

Checks numeric variables only end in one of "_currency", "official","parallel", "year”
Also checks if there are any non-numeric variables with these suffixes.

Returns an `error` if any infringing columns were found.