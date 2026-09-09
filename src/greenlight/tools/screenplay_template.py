"""Title-page skeleton generator for blank-screenplay creation."""

from datetime import date


def TITLE_PAGE_SKELETON(
    title: str,
    author: str = "",
    credit: str = "Written by",
    source: str = "",
    draft_date: str = "",
    contact: str = "",
    genre: str = "",
) -> str:
    """Generate a Fountain title-page + blank body for a new screenplay.

    Returns a valid Fountain document with title page metadata and no scenes,
    ready for the writer to begin.
    """
    if not draft_date:
        draft_date = date.today().isoformat()

    lines = [
        f"Title: {title}",
        f"Credit: {credit}" if credit else None,
        f"Author: {author}" if author else None,
        f"Source: {source}" if source else None,
        f"Draft date: {draft_date}",
        f"Contact: {contact}" if contact else None,
        f"Genre: {genre}" if genre else None,
        "",
        "",
    ]

    return "\n".join(line for line in lines if line is not None)
