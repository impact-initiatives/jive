from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AvatarUrls(BaseModel):
    model_config: ConfigDict = ConfigDict(populate_by_name=True)

    x16x16: str = Field(validation_alias="16x16")
    x24x24: str = Field(validation_alias="24x24")
    x32x32: str = Field(validation_alias="32x32")
    x48x48: str = Field(validation_alias="48x48")


class AuthorInfo(BaseModel):
    accountId: str
    accountType: str
    active: bool
    avatarUrls: AvatarUrls
    displayName: str
    key: str | None = None
    name: str | None = None
    self: str | None = None


class IssueAttachment(BaseModel):
    author: AuthorInfo
    content: str
    created: str
    filename: str
    id: int
    mimeType: str
    self: str
    size: int
    thumbnail: str | None = None


class ProjectCategory(BaseModel):
    description: str
    id: str
    name: str
    self: str


class InsightInfo(BaseModel):
    lastIssueUpdateTime: str
    totalIssueCount: int


class Project(BaseModel):
    avatarUrls: AvatarUrls
    id: str
    insight: InsightInfo
    key: str
    name: str
    projectCategory: ProjectCategory
    self: str
    simplified: bool
    style: str


class TimeTracking(BaseModel):
    originalEstimate: str
    originalEstimateSeconds: int
    remainingEstimate: str
    remainingEstimateSeconds: int
    timeSpent: str
    timeSpentSeconds: int


class Watcher(BaseModel):
    isWatching: bool
    self: str
    watchCount: int


class SubTaskOutwardIssue(BaseModel):
    fields: dict[str, Any] = Field(default_factory=dict)
    id: str
    key: str
    self: str


class LinkType(BaseModel):
    id: str
    inward: str
    name: str
    outward: str


class SubTaskEntry(BaseModel):
    id: str
    outwardIssue: SubTaskOutwardIssue
    type: LinkType


class DescriptionBody(BaseModel):
    type: str
    version: int
    content: list[Any] = Field(default_factory=list)


class Comment(BaseModel):
    author: AuthorInfo
    body: DescriptionBody
    created: str
    id: str
    self: str
    updateAuthor: AuthorInfo
    updated: str | None = None
    visibility: dict[str, Any] | None = None


class Worklog(BaseModel):
    author: AuthorInfo
    comment: DescriptionBody
    id: str
    issueId: str
    self: str
    started: str
    timeSpent: str
    timeSpentSeconds: int
    updateAuthor: AuthorInfo
    updated: str
    visibility: dict[str, Any] | None = None


class IssueLink(BaseModel):
    id: str
    type: LinkType
    outwardIssue: dict | None = None
    inwardIssue: dict | None = None


class FieldsData(BaseModel):
    watcher: Watcher | None = None
    attachment: list[IssueAttachment] = Field(default_factory=list)
    sub_tasks: list[SubTaskEntry] = Field(default_factory=list, alias="sub-tasks")
    description: DescriptionBody | None = None
    project: Project | None = None
    comment: list[Comment] = Field(default_factory=list)
    issuelinks: list[IssueLink] = Field(default_factory=list)
    worklog: list[Worklog] = Field(default_factory=list)
    updated: int | None = None
    timetracking: TimeTracking | None = None

    # class Config:
    #     populate_by_name = True


class IssueResponse(BaseModel):
    fields: FieldsData | None = None
    id: str | None = None
    key: str | None = None


class IssueAttachmentResponse(BaseModel):
    attachments: list[IssueAttachment] = Field(default_factory=list)


class TemporaryAttachment(BaseModel):
    temporaryAttachmentId: str
    filename: str | None = None


class TemporaryAttachmentsResponse(BaseModel):
    temporaryAttachments: list[TemporaryAttachment] = Field(default_factory=list)


class ServiceDeskResponse(BaseModel):
    id: str
    projectId: str
    projectName: str
    projectKey: str
    _links: dict[str, str]


class FormTemplate(BaseModel):
    id: str


class Form(BaseModel):
    formTemplate: FormTemplate
    id: str
    internal: bool
    lock: bool
    name: str
    submitted: bool
    updated: str


class SubmitSettings(BaseModel):
    lock: bool
    pdf: bool


class DesignSettings(BaseModel):
    language: str
    name: str
    primaryLocale: str
    submit: SubmitSettings
    translatedLocale: str


class Design(BaseModel):
    conditions: dict[str, Any] = Field(default_factory=dict)
    layout: list[dict[str, Any]] = Field(default_factory=list)
    questions: dict[str, Any] = Field(default_factory=dict)
    sections: dict[str, Any] = Field(default_factory=dict)
    settings: DesignSettings


class State(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict)
    status: str
    visibility: str


class FormDocument(BaseModel):
    design: Design
    id: str
    state: State
    updated: str
