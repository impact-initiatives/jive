from pydantic import AliasChoices, BaseModel, Field

from ..validators.base import ValidatorResponse

# Not actually used by argus but can be used to map the dict/json output into a pydantic model


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
    admin_errors: list[ValidatorResponse] = Field(
        default_factory=list, validation_alias=AliasChoices("admin_errors", "admin_error")
    )
    admin_info: list[ValidatorResponse] = Field(default_factory=list)
    errors: list[ValidatorResponse] = Field(
        default_factory=list, validation_alias=AliasChoices("errors", "error")
    )
    warnings: list[ValidatorResponse] = Field(
        default_factory=list, validation_alias=AliasChoices("warnings", "warning")
    )
    info: list[ValidatorResponse] = Field(default_factory=list)
    passed: list[ValidatorResponse] = Field(default_factory=list)
    metadata: MetadataModel
