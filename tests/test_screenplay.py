import uuid

import pytest
from fastapi.testclient import TestClient

from greenlight.api.app import app


@pytest.fixture
def client():
    return TestClient(app)


SAMPLE = """INT. DINER - NIGHT

Rain hammers the window. SARAH sits alone with cold coffee.

SARAH
(quietly)
You said you'd call.

JOE
I know what I said.

CUT TO:

EXT. PARKING LOT - CONTINUOUS

Joe follows her into the rain.

JOE
Wait!
"""


@pytest.fixture
def script_id(client):
    sid = f"test_{uuid.uuid4().hex[:12]}"
    import hashlib

    from greenlight.db.client import get_ch_client, insert

    insert(
        "scripts",
        [
            {
                "id": sid,
                "title": "Repo Test",
                "author": "t",
                "genre": "",
                "hash": hashlib.sha256(SAMPLE.encode()).hexdigest()[:16],
                "owner": "local",
            },
        ],
    )
    yield sid
    get_ch_client().command(
        "DELETE FROM greenlight.scripts WHERE id = %(sid)s",
        parameters={"sid": sid},
    )


class TestFountainDocument:
    def test_parse_document_types(self):
        from greenlight.tools.fountain_document import parse_document

        elements = parse_document(SAMPLE)
        types = [e.type for e in elements]
        assert types[0] == "scene_heading"
        assert "character" in types
        assert "dialogue" in types
        assert "transition" in types
        assert elements[-1].type == "dialogue"

    def test_scene_numbering(self):
        from greenlight.tools.fountain_document import parse_document

        elements = parse_document(SAMPLE)
        headings = [e for e in elements if e.type == "scene_heading"]
        assert len(headings) == 2
        assert headings[0].scene_number == 1
        assert headings[1].scene_number == 2

    def test_render_roundtrip(self):
        from greenlight.tools.fountain_document import parse_document, render_document

        elements = parse_document(SAMPLE)
        rendered = render_document([e.__dict__ | {"ordinal": e.ordinal} for e in elements])
        reparsed = parse_document(rendered)
        assert [e.text for e in reparsed] == [e.text for e in elements]

    SPEC_SAMPLE = """Title: The Greenlight
Credit: Written by
Author: Jane Writer
Contact info:
    jane@example.com
    555-0100

===

INT. LAB - NIGHT

/* this boneyard is dropped */

# Act One

= Sarah realizes the truth.

[[check continuity here]]

>centered text<

@narrator (V.O.)
They were wrong.

!A light flickers on. Not forced at all.

SMASH CUT TO:

> CUT TO EXT.

INT. DINER - DAY #7#

SARAH^
You came.
"""

    def test_spec_title_page(self):
        from greenlight.tools.fountain_document import parse_document

        elements = parse_document(self.SPEC_SAMPLE)
        title = [e for e in elements if e.type == "title_page"]
        assert len(title) == 4
        assert title[0].character_name == "Title"
        assert "The Greenlight" in title[0].text
        # multi-line contact value folded into one element
        assert "jane@example.com" in title[3].text and "555-0100" in title[3].text
        # page break '===' treated as transition, not action noise
        assert any(e.type == "transition" and e.text == "===" for e in elements)

    def test_spec_boneyard_dropped(self):
        from greenlight.tools.fountain_document import parse_document

        elements = parse_document(self.SPEC_SAMPLE)
        assert not any("boneyard" in e.text for e in elements)

    def test_spec_section_synopsis_note_centered(self):
        from greenlight.tools.fountain_document import parse_document

        types = [e.type for e in parse_document(self.SPEC_SAMPLE)]
        assert types.count("section") == 1
        assert types.count("synopsis") == 1
        assert types.count("note") == 1
        assert types.count("centered") == 1

    def test_spec_forced_elements(self):
        from greenlight.tools.fountain_document import parse_document

        elements = parse_document(self.SPEC_SAMPLE)
        narrator = next(e for e in elements if e.character_name.startswith("narrator"))
        assert narrator.type == "character"
        assert narrator.text.startswith("@narrator")
        flicker = next(e for e in elements if e.text.startswith("!"))
        assert flicker.type == "action"

    def test_spec_dual_dialogue_marker_tolerated(self):
        from greenlight.tools.fountain_document import parse_document

        elements = parse_document(self.SPEC_SAMPLE)
        cue = next(e for e in elements if "^" in e.text)
        assert cue.type == "character"
        assert cue.character_name == "SARAH"

    def test_spec_scene_number_kept_verbatim(self):
        from greenlight.tools.fountain_document import parse_document, summarize_scenes

        elements = parse_document(self.SPEC_SAMPLE)
        diner = next(e for e in elements if e.type == "scene_heading" and "DINER" in e.text)
        assert "#7#" in diner.text
        headings = summarize_scenes(elements)
        assert any("#7#" not in s["heading"] and "DINER" in s["heading"] for s in headings)

    def test_spec_generic_uppercase_transition(self):
        from greenlight.tools.fountain_document import parse_document

        elements = parse_document(self.SPEC_SAMPLE)
        transitions = [e.text for e in elements if e.type == "transition"]
        assert "SMASH CUT TO:" in transitions
        assert "> CUT TO EXT." in transitions


class TestScreenplayRepo:
    def test_load_creates_repo(self, client, script_id):
        res = client.post(
            f"/api/scripts/{script_id}/load", json={"author": "tester", "raw_text": SAMPLE}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["loaded"] is True
        assert data["scene_count"] == 2
        assert data["branch_id"]
        assert data["version_id"]

    def test_load_idempotent(self, client, script_id):
        client.post(f"/api/scripts/{script_id}/load", json={"raw_text": SAMPLE})
        res = client.post(f"/api/scripts/{script_id}/load", json={"raw_text": SAMPLE})
        assert res.json().get("already_loaded") is True

    def test_load_missing_script(self, client):
        res = client.post("/api/scripts/does-not-exist/load", json={"raw_text": SAMPLE})
        assert res.status_code == 404

    def test_repo_state(self, client, script_id):
        client.post(f"/api/scripts/{script_id}/load", json={"raw_text": SAMPLE})
        res = client.get(f"/api/scripts/{script_id}/repo")
        data = res.json()
        assert data["loaded"] is True
        assert len(data["branches"]) == 1
        assert data["branches"][0]["name"] == "main"
        assert len(data["versions"]) == 1

    def test_version_detail_has_scenes_with_text(self, client, script_id):
        load = client.post(f"/api/scripts/{script_id}/load", json={"raw_text": SAMPLE}).json()
        detail = client.get(f"/api/versions/{load['version_id']}").json()
        assert len(detail["scenes"]) == 2
        s1 = detail["scenes"][0]
        assert s1["num"] == 1
        assert "INT. DINER - NIGHT" in s1["text"]
        assert "You said you'd call." in s1["text"]
        # scene text does not bleed into next scene
        assert "PARKING LOT" not in s1["text"]

    def test_commit_scene_replacement(self, client, script_id):
        load = client.post(f"/api/scripts/{script_id}/load", json={"raw_text": SAMPLE}).json()
        base_vid = load["version_id"]
        branch_id = load["branch_id"]

        commit = client.post(
            f"/api/scripts/{script_id}/versions",
            json={
                "branch_id": branch_id,
                "base_version_id": base_vid,
                "message": "Sharpen Sarah's line",
                "author": "writer",
                "scene": {
                    "number": 1,
                    "text": """INT. DINER - NIGHT

Rain hammers the window. SARAH sits alone with cold coffee.

SARAH
(quietly)
You said you'd call.
And you never did.

JOE
I know what I said.""",
                },
            },
        ).json()
        assert commit.get("unchanged") is not True
        new_vid = commit["version_id"]

        scenes = client.get(f"/api/versions/{new_vid}").json()["scenes"]
        s1 = next(s for s in scenes if s["num"] == 1)
        assert "And you never did." in s1["text"]
        # other scene untouched (modulo join whitespace)
        raw_base = client.get(f"/api/versions/{base_vid}/fountain").text
        raw_new = client.get(f"/api/versions/{new_vid}/fountain").text
        base_s2 = raw_base.split("EXT. PARKING LOT")[1].strip()
        new_s2 = raw_new.split("EXT. PARKING LOT")[1].strip()
        assert base_s2 == new_s2

        diff = client.get(f"/api/versions/{base_vid}/diff/{new_vid}").json()
        assert any(
            c["change"] == "modified" and "never did" in c.get("after", "") for c in diff["changes"]
        )

    def test_branch_revert_apply(self, client, script_id):
        load = client.post(f"/api/scripts/{script_id}/load", json={"raw_text": SAMPLE}).json()
        v1 = load["version_id"]
        main_branch = load["branch_id"]

        # edit scene 1 on main -> v2
        client.post(
            f"/api/scripts/{script_id}/versions",
            json={
                "branch_id": main_branch,
                "base_version_id": v1,
                "message": "edit",
                "scene": {"number": 1, "text": "INT. DINER - NIGHT\n\nChanged line only."},
            },
        )

        # feature branch from v1; independent edit -> v3
        branch = client.post(
            f"/api/scripts/{script_id}/branches", json={"name": "alt", "from_version_id": v1}
        ).json()
        assert branch["head_version_id"] == v1
        client.post(
            f"/api/scripts/{script_id}/versions",
            json={
                "branch_id": branch["branch_id"],
                "base_version_id": v1,
                "message": "alt edit",
                "scene": {"number": 1, "text": "INT. DINER - NIGHT\n\nAlt take of the line."},
            },
        )

        # apply alt onto main -> v4
        applied = client.post(
            f"/api/scripts/{script_id}/apply-branch",
            json={"source_branch_id": branch["branch_id"], "target_branch_id": main_branch},
        ).json()
        assert applied.get("unchanged") is not True
        assert applied["changed"] >= 1

        # revert main to v1 -> v5 (content hash equals v1)
        revert = client.post(
            f"/api/scripts/{script_id}/revert",
            json={"branch_id": main_branch, "revert_to_version_id": v1},
        ).json()
        assert revert["content_hash"] == client.get(f"/api/versions/{v1}").json()["content_hash"]

        repo = client.get(f"/api/scripts/{script_id}/repo").json()
        assert {b["name"] for b in repo["branches"]} == {"main", "alt"}
        assert len(repo["versions"]) == 5

    def test_session_active_flow(self, client, script_id):
        load = client.post(f"/api/scripts/{script_id}/load", json={"raw_text": SAMPLE}).json()
        session = client.get("/api/session/active").json()
        assert session["loaded"] is True
        assert session["script_id"] == script_id
        assert session["version_id"] == load["version_id"]

        client.put(
            f"/api/scripts/{script_id}/active",
            json={"branch_id": load["branch_id"], "version_id": ""},
        )
        session = client.get("/api/session/active").json()
        assert session["version_id"] == ""

    def test_unload(self, client, script_id):
        client.post(f"/api/scripts/{script_id}/load", json={"raw_text": SAMPLE})
        res = client.post(f"/api/scripts/{script_id}/unload")
        assert res.status_code == 200
        session = client.get("/api/session/active").json()
        assert session["loaded"] is False


class TestCoverageLatest:
    def test_latest_coverage(self, client, script_id):
        import json as _json

        from greenlight.db.client import insert

        insert(
            "coverage",
            [
                {
                    "script_id": script_id,
                    "verdict": "RECOMMEND",
                    "logline": "Test logline.",
                    "synopsis": "Test synopsis.",
                    "scores": _json.dumps({"plot": "Tight."}),
                    "analyst_notes": "Sharp the second act.",
                }
            ],
        )
        res = client.get(f"/api/scripts/{script_id}/coverage/latest")
        assert res.status_code == 200
        data = res.json()
        assert data["verdict"] == "RECOMMEND"
        assert data["comments"] == {"plot": "Tight."}

    def test_latest_coverage_missing(self, client):
        res = client.get("/api/scripts/no-such/coverage/latest")
        assert res.status_code == 404

    def test_latest_coverage_none_yet_is_found_false(self, client):
        """Existing script with no coverage runs is an empty state, not an error."""
        import uuid as _uuid

        from greenlight.db.client import command, insert

        sid = f"cov-latest-{_uuid.uuid4().hex[:8]}"
        insert(
            "scripts",
            [{"id": sid, "title": "No coverage yet", "author": "t", "hash": "", "owner": "local"}],
        )
        try:
            res = client.get(f"/api/scripts/{sid}/coverage/latest")
            assert res.status_code == 200
            assert res.json() == {"found": False}
        finally:
            command("DELETE FROM greenlight.scripts WHERE id = %(sid)s", {"sid": sid})


class TestSystemSchema:
    def test_schema_introspection(self, client):
        res = client.get("/api/system/schema")
        assert res.status_code == 200
        names = {t["name"] for t in res.json()["tables"]}
        assert {"scripts", "script_versions", "script_branches"} <= names
