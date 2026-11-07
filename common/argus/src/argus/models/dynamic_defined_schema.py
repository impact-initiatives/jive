from pathlib import Path, PosixPath
from typing import override

from ..models.base_dataset import BaseDataset
from ..utils.logging import get_logger
from ..utils.yaml_loader import load_file
from ..validators.base import BaseValidator, SortedSheets, ValidationResult

logger = get_logger("argus.build_dataset")


class DynamicDefinedDataset(BaseDataset):
    """
    This class:
    - appends sheet specific common validators to the list of existing validators
        based on the sheets in the schema and their classifications.

        This allows these validators to be created dynamically instead of
        maintaining a large list in a config file - useful for when
        there are several repeat_group sheets

    - removes items from a schema if the item was not loaded based on
        sheet prefixes and suffixes stored in the config folder for the
        programme_type.

        This is useful for when it is unknown which repeat_groups a dataset
        will contain but it is known what the allowed repeat_groups are.
        For example, in the msna schema.yaml file we can specify repeat_group
        sheets for healh (health_clean_data, health_raw_data etc) but then
        if a particualr dataset doesnt include that repeat_group then
        the schema objects can be removed.

        If a sheet has just not been named correctly it will show up
        in the unexpected sheet check.


    """

    def __init__(self, schema_path: Path | str, validator_path: Path | str) -> None:
        super().__init__(schema_path, validator_path)
        self.sorted_sheets: SortedSheets = SortedSheets()

    @override
    def process_data(self, **kwargs: int | str | float | Path) -> list[ValidationResult]:
        """Runs all the steps."""
        all_results: list[ValidationResult] = []

        dataset_config_directory = kwargs["dataset_config_directory"]
        if type(dataset_config_directory) is PosixPath:
            try:
                sheet_options, _ = load_file(
                    dataset_config_directory
                    / self.schema.programme_type
                    / "config/sheet_options.yaml"
                )
                self.update_schema(sheet_options)

            except Exception:
                logger.info(
                    "No sheet prefixes found. Schema left unchanged.",
                    extra={"file": dataset_config_directory / "config/sheet_options.yaml"},
                )

        # this must come after update_schema
        # to ensure the complete schema is referenced
        self.validators: list[BaseValidator] = self.get_validators()
        self.build_validators()

        results = self.validate_schema_links()
        if results:
            all_results.extend(results)

        return all_results

    def update_schema(self, sheet_options: dict):
        """
        Remove sheet prefix/sheet_type combinations from the schema
        if they exist and an excel sheet with that name was not loaded.
        """
        allowed_prefixes: list[str] = sheet_options["prefixes"]
        sheet_types: list[str] = sheet_options["sheet_type"]

        for prefix, sheet_type in [
            (prefix, sheet_type) for prefix in allowed_prefixes for sheet_type in sheet_types
        ]:
            loaded_sheet = self.data.get_loaded_sheet(prefix + sheet_type)
            if loaded_sheet is None:
                removed = self.schema.remove_loaded_sheet(prefix + sheet_type)
                if removed:
                    logger.info(
                        f"Sheet '{prefix + sheet_type}' removed from schema as it was not loaded.",
                    )
