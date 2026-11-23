from typing import Any

from pydantic import AliasChoices, BaseModel, Field


class ResultItemModel(BaseModel):
    rule: str
    message: str
    severity: str
    sheet_name: str | None = None
    column_name: str | None = None
    details: dict[str, Any] | None = None

    def get_details_length(self, default_return_value: int = 1):
        "Returns default_return_value = 1 as in there is only one issue and its the message."
        if self.details is None:
            return default_return_value
        return len(next(iter(self.details.values())))


class SummaryModel(BaseModel):
    passed: int
    admin_errors: int = Field(validation_alias=AliasChoices("admin_errors", "admin_error"))
    admin_info: int
    errors: int = Field(validation_alias=AliasChoices("errors", "error"))
    warnings: int = Field(validation_alias=AliasChoices("warnings", "warning"))
    info: int


class MetadataModel(BaseModel):
    output_type: str
    programme_type: str
    validation_date: str
    file_name: str


class PipelineResponse(BaseModel):
    """The strictly typed output of the ValidationPipeline."""

    success: bool
    summary: SummaryModel
    admin_errors: list[ResultItemModel] = Field(
        default_factory=list, validation_alias=AliasChoices("admin_errors", "admin_error")
    )
    admin_info: list[ResultItemModel] = Field(default_factory=list)
    errors: list[ResultItemModel] = Field(
        default_factory=list, validation_alias=AliasChoices("errors", "error")
    )
    warnings: list[ResultItemModel] = Field(
        default_factory=list, validation_alias=AliasChoices("warnings", "warning")
    )
    info: list[ResultItemModel] = Field(default_factory=list)
    passed: list[ResultItemModel] = Field(default_factory=list)
    metadata: MetadataModel
