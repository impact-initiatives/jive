# Argus: Implemented Validation Rules

This is a brief overview of the validation rules that have been implemented. The implementation of these rules can be found in `validarors/common_validators` or under `validators/programme_type` for programme specific checks like `jmmi` within the Argus repository.

Validation rules are designed to be run independently. This can result in some overlap in the validation checks and can lead to duplicate validation messages. For example, if a sheet is expected for multiple rules but not found then an error will be generated for each rule that can not find this sheet.

Each rule check within a validator returns a result message and an associated severity. Most validation messages that report a result with an error or warning severity will provide further details. This could include a list of infringing records, a list of missing sheets etc.





