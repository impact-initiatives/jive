## JMMI Column Name Checks

JMMI columns have [naming standards](https://acted.sharepoint.com/:x:/r/sites/IMPACT-Public_Services_Markets_Infrastructure/Shared%20Documents/Cash%20and%20Markets/Toolbox/Internal%20resources/1.%20Toolkits%20and%20guidance/JMMI/6.%20Data%20standardization%20guidelines/JMMI%20Minimum%20Data%20Standards/02_DICTIONARY_2024_JMMI_minimum_data_standards.xlsx?d=w3b0c300fc9c244c2b6bd0ed556f23e29&csf=1&web=1&e=UhA7Jv). These checks validate the column names in the `clean_data` sheet against the naming standards. Many of these rules reference dictionary items that are maintained in the [Argus Schemas repository](https://github.com/impact-initiatives/argus_schemas/tree/main/jmmi/config).

**Implementation**: `jmmi/column_name_validator.py`

**Rule name:** `JMMIColumnNameCheck`

**Check 1 (B001, B002)**

Checks that:

- country specific variables have an appropriate prefix (2B.d5_ISO_codes_prefix)
- country specific variables have an appropriate suffix (2B.g2_variable_suffix)

Returns an `error` if any infringing columns were found.

**Check 2 (B003)**

Checks if country specific variables have item (2B.d2_good_renaming) and column names (2B.d1_item_standard_column_name) that have been standardised. 

Returns an `error` if any infringing columns were found.

**Check 3 (B004)**

Checks that items are in the goods dictionary (2B.d2_good_renaming)

Returns an `error` if any items were not found in the dictionary.

**Check 4** 

Checks if non-country specific item variables have column names that are not in the column name dictionary (2B.d1_item_standard_column_name)

Returns an `error` if any records were not found in the dictionary.

**Check 5 (E001)**

Checks that certain columns have been removed.

Returns an `error` if any infringing columns were found.