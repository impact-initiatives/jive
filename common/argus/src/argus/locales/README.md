# Translation File Management
This guide covers the creation and management of translation files used in this project. 

## How Translations are supported
Internationalisation (I18N) and localisation (L10N) services are provided through the [`gettext`](https://docs.python.org/3/library/i18n.html) python module. Through this module, validation messages can be written in multiple languages. The correct messages can be returned to the user based on the paramaters used to run the validation process.

## Using an existing message/key
To use an existing message a few steps need to be followed. 
1. Import the helper method if not already done. Note, some base classes like `BaseValidator` already contain a helper function. 
```python
from locales.il8n import _
```
2. Set a key and the required parameters. For a `ValidationResult` this would look something like this:
```python
ValidationResult(
    rule=rule,
    message=_(
        "data_helpers.get_data_loaded_column",  # key
        column="some_column",  # parameters, if required
        sheet="some_sheet",
    ),
    severity=SeverityLevel.ERROR,
    sheet_name="some_sheet",
    column_name="some_column",
)
```
or if a base class already has a helper function:
```python
ValidationResult(
    rule=self.name,
    message=self._(
        "duplicate_sheet_match_validator.duplicate_sheets",  # key
        count=100,  # parameters, if required
    ),
    severity=SeverityLevel.ERROR,
    details=some_details_df.to_dict(),
)
```
- The key should be an existing key in the `.po` file.
- A message does not have to have parameters. 
- Parameters can have any name but the name has to be referenced in the message `.po` file.

## Adding a new message to translation files
If adding an entirly new (unique) key, the steps in the previous section can first be followed. Once this is done the following steps should be followed.

3. Once all the changes have been saved the template file can be generated. In a terminal, this can be done for one file (set the file path as required):

```bash
xgettext -d base -o locales/messages.pot your/file/path.py
```
For example:
```bash
xgettext -d base -o locales/messages.pot src/argus/validators/schema_validators/unexpected_sheets_validator.py 
```

or for multiple files
```bash
xgettext -d base -o locales/messages.pot your/files/*.py
```
For example:
```bash
xgettext -d base -o locales/messages.pot src/argus/validators/schema_validators/*.py
```
The output will be stored in `locales/messages.pot` and will contain the keys from the file and an empty message string
```
#: src/argus/validators/data_helpers.py:88
msgid "data_helpers.get_data_loaded_column"
msgstr ""
```
These can be coppied into the relevant `.po` file, for example `en/LC_MESSAGES/messages.po`

4. Set the message. The parameters can be set in the message between `{}`. The paramaters must match those used when calling the method. 
```
#: src/argus/validators/data_helpers.py:88
msgid "data_helpers.get_data_loaded_column"
msgstr "A column for '{column}' in sheet '{sheet}' is expected."
```
5. Once all the messages have been set, the `.mo` file needs to be generated. Using the terminal run the following for the appropriate language:

```bash
msgfmt -o locales/en/LC_MESSAGES/messages.mo locales/en/LC_MESSAGES/messages.po
```
6. Commit changes to the repository.

## Translate an existing message
If there is an existing message in one language and a translation is required then the process is a little easier. 

Language translation files are separated by directory. For example, English translations are stored in `locales/en/LC_MESSAGES/`. To add support for more languages the relevant folder structure needs to be created. For example, to add French the directory `locales/fr/LC_MESSAGES/` would have to be created. A `messages.po` file will also need to be created with the correct header contents - the header from the English `.po` file can be copied and modified as required. This file should be stored in the newly created directory. For example, `locales/fr/LC_MESSAGES/messages.po`. 

Once the directory and file exist:

1. Copy the existing message (msgid, msgstr) into the relevant language file. For example, from `en/LC_MESSAGES/messages.po` to `fr/LC_MESSAGES/messages.po`
2. Translate the contents of msgstr. Note:
    - DO NOT change the text between the curley braces `{}`.
    - The position of the curley braces `{}` can change as required.

For example, this:
```
#: src/argus/validators/data_helpers.py:88
msgid "data_helpers.get_data_loaded_column"
msgstr "A column for '{column}' in sheet '{sheet}' is expected."
```
will change to this:
```
#: src/argus/validators/data_helpers.py:88
msgid "data_helpers.get_data_loaded_column"
msgstr "French translation '{column}' French translation '{sheet}' French translation."
```
3. Once all the translations have been done, rebuild the `.mo` file. Using the terminal and referencing the relevant locale (in this case fr):

```bash
msgfmt -o locales/fr/LC_MESSAGES/messages.mo locales/fr/LC_MESSAGES/messages.po
```
4. Commit changes to the repository.