import uuid

from ..worker.jira.models import AuthorInfo, AvatarUrls, IssueAttachment


def make_issue_response(
    issue_key: str = "RQA-123",
    issue_id: str | int = 10001,
    attachment_count: int = 0,
    attachments: list[dict] | None = None,
    project_key: str = "RQA",
    updated: int = 1672531200000,
) -> dict:
    """Create minimal valid IssueResponse dict for tests.

    Args:
        issue_key: Jira issue key (e.g., "RQA-123")
        issue_id: Issue ID (str or int accepted)
        attachment_count: Number of placeholder attachments to generate
        attachments: Custom attachment dicts (overrides attachment_count)
        project_key: Project key for the embedded project object
        updated: Timestamp integer for the 'updated' field

    Returns:
        Dict suitable for responses.add(..., json=...) or model_validate()
    """

    def make_project(key: str) -> dict:
        """Minimal valid Project."""
        return {
            "avatarUrls": {"16x16": "-", "24x24": "-", "32x32": "-", "48x48": "-"},
            "id": str(uuid.uuid4().hex[:6]),
            "insight": {
                "lastIssueUpdateTime": "2021-04-22T05:37:05.000+0000",
                "totalIssueCount": 0,
            },
            "key": key,
            "name": f"{key} Project",
            "projectCategory": {"description": "", "id": "10000", "name": "General", "self": "-"},
            "self": "-",
            "simplified": False,
            "style": "classic",
        }

    def make_attachment(idx: int) -> dict:
        """Single minimal attachment with required fields."""
        return {
            "id": idx,
            "filename": f"file_{idx}.xlsx",
            "content": f"https://example.com/content/{idx}",
            "created": "2026-05-01T10:00:00.000+0000",
            "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "self": f"https://example.com/attachment/{idx}",
            "size": 1000,
            "thumbnail": f"https://example.com/thumb/{idx}",
            "author": {
                "accountId": f"user-{idx}",
                "accountType": "atlassian",
                "active": True,
                "avatarUrls": {"16x16": "-", "24x24": "-", "32x32": "-", "48x48": "-"},
                "displayName": "Test User",
                "key": "",
                "name": "",
                "self": "-",
            },
        }

    # Build attachments list
    if attachments is not None:
        attach_list = attachments
    elif attachment_count > 0:
        attach_list = [make_attachment(i) for i in range(1, attachment_count + 1)]
    else:
        attach_list = []

    payload = {
        "fields": {
            "attachment": attach_list,
            "comment": [],
            "issuelinks": [],
            "worklog": [],
            "project": make_project(project_key),
            "updated": updated,
        },
        "id": str(issue_id),
        "key": issue_key,
    }

    # Merge any extra fields from caller
    return payload


def make_attachment(
    filename: str = "file.xlsx",
    content: str = "https://example.com/file.xlsx",
    created: str = "2026-05-01T10:00:00.000+0000",
    id: int = 10000,
    mime_type: str | None = None,
    size: int = 1000,
) -> IssueAttachment:

    # Infer MIME type from extension
    if mime_type is None:
        ext = filename.lower().split(".")[-1]
        mime_map = {
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "xls": "application/vnd.ms-excel",
            "pdf": "application/pdf",
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "txt": "text/plain",
            "zip": "application/zip",
        }
        mime_type = mime_map.get(ext, "application/octet-stream")

    # Extract initials from filename for avatar
    initials = "".join([c.upper() for c in filename[:3] if c.isalpha()]) or "AA"

    return IssueAttachment(
        id=id,
        filename=filename,
        content=content,
        created=created,
        mimeType=mime_type,
        self=f"https://example.com/rest/api/3/attachments/{id}",
        size=size,
        thumbnail=f"https://example.com/thumb/{id}",
        author=AuthorInfo(
            accountId=f"user-{id:06d}",
            accountType="atlassian",
            active=True,
            avatarUrls=AvatarUrls(
                x16x16=f"https://avatar.example.com/{initials}-16.png",
                x24x24=f"https://avatar.example.com/{initials}-24.png",
                x32x32=f"https://avatar.example.com/{initials}-32.png",
                x48x48=f"https://avatar.example.com/{initials}-48.png",
            ),
            displayName=f"User {initials}",
            key="",
            name="",
            self=f"https://example.com/user?id={id}",
        ),
    )
