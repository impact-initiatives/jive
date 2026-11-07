from pathlib import Path

import fastexcel
import polars as pl

from ..loaders.base_excel_loader import ExcelLoaderData
from ..models.base_dataset_schemas import BaseDatasetSchema
from ..validators.base import SeverityLevel, ValidationResult
from .base import (
    DataSheetMap,
)
from .base_excel_loader import BaseExcelLoader


class ExcelLoader(BaseExcelLoader):
    def __init__(self, schema_config: BaseDatasetSchema):
        self.schema: BaseDatasetSchema = schema_config

    def load(
        self, filepath: Path, load_all_sheets: bool = False
    ) -> tuple[ExcelLoaderData, list[ValidationResult]]:
        """Loads an excel file, does some checking and sorting of the sheets.

        Args:
            filepath (Path): Filepath of excel file. Might change for api call.
            load_all_sheets (bool): loaded all unmapped sheets. used for dynamic
                schema generation. Defaults to 'False'
        Returns:
            tuple[ExcelLoaderData,  List[ValidationResult]]:
            class that contains the loaded data, sheets etc,
            list of validation warnings

        """
        results: list[ValidationResult] = []
        # get a list of excel sheet names
        excel_file = fastexcel.read_excel(filepath)
        all_sheets = excel_file.sheet_names
        # lower sheet names for easier comparison later
        # all_sheets = list(map(str.lower, all_sheets))

        data = ExcelLoaderData()

        def _load_excel_sheet(
            excel_file: fastexcel.ExcelReader, sheet_name: str, schema_sheet_name: str | None = None
        ) -> bool:
            excel_sheet = excel_file.load_sheet(
                sheet_name, whitespace_as_null=True, skip_whitespace_tail_rows=True
            )

            # check hidden sheets
            if excel_sheet.visible != "visible":
                data.hidden_sheets.append(sheet_name)
            data_df: pl.DataFrame = excel_sheet.to_polars()

            # check un-named columns (likely should be removed)
            # remove these as they will cause problems
            unnamed_columns = [
                {"sheet": sheet_name, "column_index": column.index, "name": column.name}
                for column in excel_sheet.selected_columns
                if "__UNNAMED__" in column.name
            ]

            if unnamed_columns:
                data_df = data_df.drop([str(column["name"]) for column in unnamed_columns])
                results.append(
                    ValidationResult(
                        rule="Unnamed sheet columns",
                        message=self._(
                            "excel_loader._load_excel_sheet.unnamed_columns",
                            sheet=sheet_name,
                            count=len(unnamed_columns),
                        ),
                        severity=SeverityLevel.WARNING,
                        sheet_name=sheet_name,
                        details=pl.DataFrame(unnamed_columns).to_dict(as_series=False),
                    )
                )

            result = self.check_duplicate_columns(data_df.columns, excel_sheet_name)
            # if there are duplicates then the rename function below will fail
            if result is not None:
                results.append(result)
                return False

            data_df = data_df.rename(str.lower)
            if schema_sheet_name is not None:
                schema_sheet = self.schema.get_schema_loaded_sheet(schema_sheet_name)
                if schema_sheet is not None:
                    column_results, column_matches = self.match_excel_columns_to_schema(
                        data_df.columns, schema_sheet
                    )
                    data.loaded_sheets.append(
                        DataSheetMap(
                            schema_sheet_name=l_mapped_name,
                            data_sheet_name=excel_sheet_name,
                            data=data_df,
                            column_map=column_matches,
                            original_column_names=[
                                item.name
                                for item in excel_sheet.available_columns()
                                if item.name not in [column["name"] for column in unnamed_columns]
                            ],
                        )
                    )
                    results.extend(l_results)
                    results.extend(column_results)

                else:
                    results.append(
                        ValidationResult(
                            rule="Getting Schema Sheet",
                            message=self._(
                                "helpers.get_loaded_sheet", sheet=l_mapped_name, sheet_type="excel"
                            ),
                            severity=SeverityLevel.ERROR,
                            sheet_name=l_mapped_name,
                        )
                    )
                    return False
            else:
                data.loaded_sheets.append(
                    DataSheetMap(
                        schema_sheet_name=excel_sheet_name,
                        data_sheet_name=excel_sheet_name,
                        data=data_df,
                        auto_loaded=True,
                        original_column_names=[
                            item.name
                            for item in excel_sheet.available_columns()
                            if item.name not in [column["name"] for column in unnamed_columns]
                        ],
                    )
                )
            return True

        for excel_sheet_name in all_sheets:
            l_mapped_name, l_results = self.match_excel_sheet_to_schema(
                excel_sheet_name, self.schema.loaded_sheets
            )
            u_mapped_name, u_results = self.match_excel_sheet_to_schema(
                excel_sheet_name, self.schema.unloaded_sheets
            )

            # pre schema validation will throw error if any sheets have matching names
            # or alternate names as well as if any columns within a sheet are
            # duplicated (via names or alternate names) so there should not be
            # both l_mapped_name and u_mapped_name for literal matches options
            # 1: l_mapped_name, not l_results > literal match on loaded sheets
            # 2: u_mapped_name, not u_results > literal match on unloaded sheets
            # 3: l_mapped_name, l_results, not u_mapped_name >
            #   fuzzy match on loaded sheets
            # 4: u_mapped_name, u_results > fuzzy match on unloaded sheets
            # 5: l_mapped_name and u_mapped_name > error fuzzy matching
            # 6: not l_mapped_name, not u_mapped_name, (u_results or l_results) >
            #   error fuzzy matching
            # 7: unexpected sheet > no matching
            # load_all_sheets: loads all sheets not loaded for steps 1-6.
            #   used for dynamic schema generation

            # 5
            if l_mapped_name and l_results and u_mapped_name and u_results:
                results.append(
                    ValidationResult(
                        rule="Match excel sheeet to schema",
                        message=self._(
                            "excel_loader.load.multiple_matches", sheet=excel_sheet_name
                        ),
                        severity=SeverityLevel.INFO,
                        sheet_name=excel_sheet_name,
                    )
                )
            # 6
            elif not l_mapped_name and not u_mapped_name and (l_results or u_results):
                results.extend(l_results)
                results.extend(u_results)

            # 1 and 3
            elif l_mapped_name and (
                not l_results
                or (l_results and (not (u_mapped_name and not u_results) or not u_mapped_name))
            ):
                # sheets that are expected and loaded for further data validation
                result = _load_excel_sheet(excel_file, excel_sheet_name, l_mapped_name)
                if not result:
                    continue

            # 2, 4
            elif u_mapped_name:
                # sheets that are expected but dont need to be loaded
                data.unloaded_sheets.append(
                    DataSheetMap(
                        schema_sheet_name=u_mapped_name,
                        data_sheet_name=excel_sheet_name,
                    )
                )
                results.extend(u_results)
            else:
                if load_all_sheets:
                    result = _load_excel_sheet(excel_file, excel_sheet_name, None)
                    if not result:
                        continue
                else:
                    # 7
                    data.unexpected_sheets.append(excel_sheet_name)

        return data, results
