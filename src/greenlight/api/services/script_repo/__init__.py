"""Script repository: persistence, parsing, branching, and active session state.

Split into:
- parsing.py: pure parse ops (scenes, scene text, diff)
- state.py:   lifecycle + active session + scaffold
- branches.py: version + branch CRUD + commit/revert/apply

Public API re-exported from __init__.py for back-compat with routes/screenplay.py.
"""

from .branches import (
    apply_branch,
    commit_version,
    create_branch,
    diff_versions,
    get_branch,
    get_branch_head,
    get_raw_fountain,
    get_version_meta,
    list_branches,
    list_versions,
    preview_apply,
    revert_version,
)
from .parsing import (
    _content_hash,
    _parse,
    _version_elements,
    diff_elements,
    get_scene_text,
    get_scenes,
    replace_scene,
)
from .state import (
    _scaffold,
    current_principal,
    delete_script,
    get_active,
    is_loaded,
    load_script,
    persist_breakdown,
    principal_var,
    record_edit,
    script_exists,
    set_active,
    unload_script,
)

__all__ = [
    "_content_hash",
    "_parse",
    "_scaffold",
    "_version_elements",
    "apply_branch",
    "commit_version",
    "create_branch",
    "current_principal",
    "delete_script",
    "diff_elements",
    "diff_versions",
    "get_active",
    "get_branch",
    "get_branch_head",
    "get_raw_fountain",
    "get_scene_text",
    "get_scenes",
    "get_version_meta",
    "is_loaded",
    "list_branches",
    "list_versions",
    "load_script",
    "persist_breakdown",
    "principal_var",
    "preview_apply",
    "record_edit",
    "replace_scene",
    "revert_version",
    "script_exists",
    "set_active",
    "unload_script",
]
