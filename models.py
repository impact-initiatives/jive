from pydantic import BaseModel, Field, ConfigDict, model_validator

class JiraSubmissionPayload(BaseModel):
    """
    Validates the custom JSON payload sent by Jira Workflow Automations 
    via the "Send web request" action.
    """
    #TO UPDATE is serves to check the payload from Jira and sort the keys. Maybe in the future there will be other keys to check.¨
    #it doesnt check if the value is correct, it just checks if the key exists
    #if it doesn't exist the field with be empty and won't throw an error since it does just sort them
    #TODO: make it throw an error if the field is empty (necessary?)

    issue_key: str = Field(..., description="The Jira Issue Key (e.g., RQA-123)")
    project_key: str = Field(default="", description="The Jira Project Key")
    rcid: str = Field(default="", description="The RCID from the ticket summary")
    dataset_type: str = Field(default="jmmi", description="The type of assessment")
    secure_link: str | None = Field(default=None, description="Optional URL to download the dataset from instead of Jira attachments")

    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def clean_dataset_type(cls, data: dict) -> dict:
        dt = data.get("dataset_type")
        if isinstance(dt, dict) and "value" in dt:
            data["dataset_type"] = dt["value"].lower()
        elif isinstance(dt, str):
            data["dataset_type"] = dt.lower()
        return data
