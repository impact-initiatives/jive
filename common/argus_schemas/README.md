**Argus Schemas**: Configuration files for [Argus](../argus/) datasets.

# About
[Argus](../argus/) performs validations on different datasets that have different schemas and validation rules. To allow these schemas to be created and managed independetly of Argus they are stored here as `yaml` files. 

# Structure
In order for schemas to properly integrate with Argus files and directories are required to follow a set structure in this repository.
```bash
type_of_programme/type_of_output/locale/schema.yaml
type_of_programme/type_of_output/locale/validators.yaml
type_of_programme/type_of_output/other/config/files.ymal
```
All folders and file names should be kept lowercase. 

For example, an English version of the jmmi dataset would contain:
```
jmmi/dataset/en/schema.yaml
jmmi/dataset/en/validators.yaml
```
`schema.yaml` contains the dataset schema. This includes the sheets, columns and other relevant properties.
`validators.yaml` contains the validation rules relevant for the dataset and their relevant properties.



# Schema
Schema files are mapped back to classes in Argus and so need to contain the same properties. Specifically, [BaseDatasetSchema](../argus/src/argus/models/base_dataset_schemas.py) and its components in [SchemaSheetMap, SchemaColumnMap and ProcessValueMap](../argus/src/argus/models/base.py).

These can be specified in `schema.yaml` directly or `schema.yaml` can import shared common components. 

```yaml
enumerator_performance_sheet:
    standard_name: "enumerator_performance_log"
    alternate_names: []
    required: false
    columns: []
```
## Common Components
Schemas often have the same requirements for sheets and columns. To reduce duplicated configuration shared components can be stored in `common/schema_defaults.yaml`. These can then be imported in schema specific files or even used within `schema_defaults.yaml` itself.

For example, within `schema_defaults` `deletion_log` makes use of `uuid_column` via `$use`.
```yaml
deletion_log:
    standard_name: "deletion_log"
    allow_fuzzy_matching: false
    columns:
      - $use: uuid_column
      - standard_name: "reason_deletion"
      - standard_name: "enum_id"

uuid_column:
    standard_name: "uuid"
    alternate_names: ["_uuid"]
    is_unique: true
    allow_fuzzy_matching: false
```
`deletion_log` can then be used as part of another schema
```yaml
_imports:
  - "../../../common/schema_defaults.yaml"

programme_type: "jmmi"
output_type: "dataset"

schema_loaded_sheets:
    - $use: deletion_log
    ...
```
it can even be modified if required. To change one of the properties:
```yaml
_imports:
  - "../../../common/schema_defaults.yaml"

programme_type: "jmmi"
output_type: "dataset"

schema_loaded_sheets:
    - $use: deletion_log
        override:
            alternate_names: ["deleted_log"]
    ...
```
or to add to one of the properties:
```yaml
_imports:
  - "../../../common/schema_defaults.yaml"

programme_type: "jmmi"
output_type: "dataset"

schema_loaded_sheets:
    - $use: deletion_log
        $append_columns:
            - $use: some_existing_column #default column
            - standard_name: "Some_new_column" #new column
                alternate_names: ["new_column"]
    ...
```
or to add a new sheet not from common
```yaml
_imports:
  - "../../../common/schema_defaults.yaml"

programme_type: "jmmi"
output_type: "dataset"

schema_loaded_sheets:
    - some_new_sheet:
        standard_name: "a_new_sheet"
        columns: []
# rest of schema...
```
A list of columns can also be specified and reused
```yaml
# in schema_defaults.yaml
admin_columns:
    - standard_name: "admin1_code"
        allow_fuzzy_matching: false
        allow_empty_values: false
    - standard_name: "admin1_label"
        allow_fuzzy_matching: false
        allow_empty_values: false

# then in the schema file
_imports:
  - "../../../common/schema_defaults.yaml"

programme_type: "jmmi"
output_type: "dataset"

schema_loaded_sheets:
    - deletion_log:
        standard_name: "deletion_log"
        columns:
        - $use: admin_columns

```


If a rule or property is specified in a file but does not exist then Argus will produce a validation error.

# Validators
Validator files are mapped back to their respective classes in Argus and so need to contain the same class names and parmaters. 

To specifiy a rule as required using default paramaters
```yaml
validators:
    - type: "MissingSheetsCheck"
    - type: "CrossSheetIdCheck"
```
or to change the paramaters based on knowledge of the schema
```yaml
validators:
    - type: "MissingSheetsCheck"
    - type: "CrossSheetIdCheck"
    - type: "CrossSheetIdCheck"
        kwargs:
            master_sheet: "clean_data"
            child_sheets: 
            - "cleaning_log"
```
Default validators can also be stored seperatly and then used
```yaml
# in validator_defaults.yaml
definitions:
  base_validators:
    - type: "MissingSheetsCheck"    
    - type: "UnexpectedSheetsCheck" 

# then in the relevant validators.yaml 
_imports:
  - "../../../common/validator_defaults.yaml"

validators:
  - $use: base_validators
```


If a rule or property is specified in a file but does not exist then Argus will produce a validation error.

# Config
Some validation rules require referencing other data like country codes and column naming configurations. These case be stored in seperate config files under the relevant programme and then referenced in the relevant validation rules. 

For example:
```
jmmi/config/iso_codes.yaml
jmmi/config/suffix_list.yaml
...
```