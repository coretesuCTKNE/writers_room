import logging
from enum import Enum

from ..db.client import query

logger = logging.getLogger(__name__)


class Role(str, Enum):
    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"


DENIAL_MESSAGE = "Studio Head protocol: You do not have clearance to access this unreleased IP."


def check_access(script_id: str, principal: str, required_role: Role) -> bool:
    rows = query(
        "SELECT role FROM greenlight.script_access WHERE script_id = %(sid)s AND principal = %(p)s",
        {"sid": script_id, "p": principal},
    )
    if not rows:
        return False
    user_role = rows[0][0]
    hierarchy = {Role.OWNER: 3, Role.EDITOR: 2, Role.VIEWER: 1}
    return hierarchy.get(Role(user_role), 0) >= hierarchy.get(required_role, 0)


def grant_access(script_id: str, principal: str, role: Role, granted_by: str = "system") -> None:
    from ..db.client import get_ch_client

    client = get_ch_client()
    client.command(
        "INSERT INTO greenlight.script_access (script_id, principal, role, granted_by) "
        "VALUES (%(sid)s, %(p)s, %(r)s, %(g)s)",
        {"sid": script_id, "p": principal, "r": role.value, "g": granted_by},
    )


def assert_access(script_id: str, principal: str, required_role: Role) -> None:
    if not check_access(script_id, principal, required_role):
        raise PermissionError(DENIAL_MESSAGE)
