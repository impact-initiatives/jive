# Argus: Implemented Validation Rules

This is a brief overview of the validation rules that have been implemented. The implementation of these rules can be found in `validarors/common_validators` or under `validators/programme_type` for programme specific checks like `jmmi`.

Because these rules are designed to be run independently, there is some overlap in the validation checks that could result in duplicate validation messages. For example, if a sheet is expected for multiple rules but not found then an error will be generated for each rule that can not find this sheet.

Most validation messages that report an error or warning will provide further details. This could include a list of infringing records, a list of missing sheets etc.

