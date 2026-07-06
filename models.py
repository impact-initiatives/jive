from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator


class JiraSubmissionPayload(BaseModel):
    """
    Validates the custom JSON payload sent by Jira Workflow Automations
    via the "Send web request" action.
    """

    # TO UPDATE is serves to check the payload from Jira and sort the keys. Maybe in the future
    # there will be other keys to check.¨
    # it doesnt check if the value is correct, it just checks if the key exists
    # if it doesn't exist the field with be empty and won't throw an error since
    # it does just sort them
    # TODO: make it throw an error if the field is empty (necessary?)

    issue_key: str = Field(..., description="The Jira Issue Key (e.g., RQA-123)")
    project_key: str = Field(default="", description="The Jira Project Key")
    rcid: str = Field(default="", description="The RCID from the ticket summary")
    dataset_type: str = Field(default="", description="The type of assessment")
    type_of_output: str = Field(default="")
    type_of_programme: str = Field(default="")
    secure_link: str | None = Field(
        default=None,
        description="Optional URL to download the dataset from instead of Jira attachments",
    )
    force_revalidation: bool = Field(
        default=False,
        description="If true, bypasses the idempotency guard and forces validation to run",
    )

    model_config: ConfigDict = ConfigDict(extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def clean_dataset_type(cls, data: dict) -> dict:
        dt = data.get("dataset_type")
        if isinstance(dt, dict) and "value" in dt:
            data["dataset_type"] = dt["value"].lower()
        elif isinstance(dt, str):
            data["dataset_type"] = dt.lower()
        return data


class ResultItemModel(BaseModel):
    rule: str
    message: str
    severity: str
    sheet_name: str | None = None
    column_name: str | None = None
    details: dict[str, Any] | None = None


class SummaryModel(BaseModel):
    passed: int
    admin_errors: int = Field(validation_alias=AliasChoices("admin_error"))
    admin_info: int
    errors: int = Field(validation_alias=AliasChoices("error"))
    warnings: int = Field(validation_alias=AliasChoices("warning"))
    info: int


class MetadataModel(BaseModel):
    dataset_type: str


class PipelineResponse(BaseModel):
    """The strictly typed output of the ValidationPipeline."""

    success: bool
    summary: SummaryModel
    admin_errors: list[ResultItemModel] = Field(
        default_factory=list, validation_alias=AliasChoices("admin_error")
    )
    admin_info: list[ResultItemModel] = Field(default_factory=list)
    errors: list[ResultItemModel] = Field(
        default_factory=list, validation_alias=AliasChoices("error")
    )
    warnings: list[ResultItemModel] = Field(
        default_factory=list, validation_alias=AliasChoices("warning")
    )
    info: list[ResultItemModel] = Field(default_factory=list)
    passed: list[ResultItemModel] = Field(default_factory=list)
    metadata: MetadataModel
