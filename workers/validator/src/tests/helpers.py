from jira.models import AuthorInfo, AvatarUrls, IssueAttachment


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
