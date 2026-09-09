"""Tests for heuristic Fountain normalization, FDX conversion, and upload pipeline."""

import pytest

from greenlight.tools.fdx_to_fountain import FdxError, convert_fdx
from greenlight.tools.fountain_normalizer import (
    beautify_fountain,
    lint_fountain,
    normalize_source,
)

MESSY_SCRIPT = """SMOKE RISING
Written by Jane Doe
1.
INT. DINER - NIGHT
Rain hammers the window. JOE sits alone,
stirring cold coffee.
JOHN
(bitter)
You shouldn't have come back.
JOE
I never left.
CUT TO:
EXT. STREET - CONTINUOUS
Empty road. Just rain.
2.
"""

CLEAN_SCRIPT = """Title: SMOKE RISING
Authors: Jane Doe

INT. DINER - NIGHT

Rain hammers the window.

JOHN
You shouldn't have come back.
"""

FONTS_FDx = """<?xml version="1.0"?>
<FountainScript Version="1.0" xmlns="http://fountain.io/sdl/StrongDet/Formatting/1_0">
<TitlePage>
<Paragraph Type="Title"><Line>GREENLIGHT</Line></Paragraph>
<Paragraph Type="Author(s)"><Line>JANE DOE</Line></Paragraph>
</TitlePage>
<Script>
<Paragraph Type="Scene Heading"><Line>INT. DINER - NIGHT</Line></Paragraph>
<Paragraph Type="Action"><Line>Rain hammers the window.</Line></Paragraph>
<Paragraph Type="Character"><Line>JOHN</Line></Paragraph>
<Paragraph Type="Parenthetical"><Line>(bitter)</Line></Paragraph>
<Paragraph Type="Dialogue"><Line>You shouldn&apos;t have come back.</Line></Paragraph>
</Script>
</FountainScript>
"""

FINAL_DRAFT_FDX = """<?xml version="1.0" encoding="UTF-8"?>
<FinalDraft DocumentType="Script" Template="No" Version="6">
<Paragraphs>
<Paragraph Type="Scene Heading"><Text>INT. OFFICE - DAY</Text></Paragraph>
<Paragraph Type="Character"><Text>BOSS</Text></Paragraph>
<Paragraph Type="Dialogue"><Text>You&apos;re fired.</Text></Paragraph>
<Paragraph Type="Transition"><Text>CUT TO:</Text></Paragraph>
<Paragraph Type="Scene Heading"><Text>EXT. PARKING LOT - DAY</Text></Paragraph>
<Paragraph Type="Action"><Text>He walks away.</Text></Paragraph>
</Paragraphs>
</FinalDraft>
"""


class TestNormalizeSource:
    def test_messy_pdf_like_text_becomes_fountain(self):
        r = normalize_source(MESSY_SCRIPT)
        assert r.changed is True
        assert "INT. DINER - NIGHT" in r.fountain
        assert "Title: SMOKE RISING" in r.fountain
        assert "Authors: Jane Doe" in r.fountain
        assert "Removed 2 page-number line(s)" in r.warnings
        assert r.stats["scenes"] == 2
        assert r.stats["cues"] == 2
        assert r.stats["dialogue_lines"] == 2
        assert r.confidence >= 0.6

    def test_clean_fountain_passes_through_untouched(self):
        r = normalize_source(CLEAN_SCRIPT)
        assert r.changed is False
        assert r.fountain == CLEAN_SCRIPT
        assert r.stats["scenes"] == 1

    def test_idempotent(self):
        first = normalize_source(MESSY_SCRIPT).fountain
        second = normalize_source(first)
        assert second.changed is False
        assert second.stats["scenes"] == 2

    def test_prose_gets_low_confidence_and_warning(self):
        r = normalize_source("The sun rose over the hills. Birds sang.\n")
        assert r.stats["scenes"] == 0
        assert r.confidence <= 0.2
        assert any("No scene headings" in w for w in r.warnings)

    def test_empty_document(self):
        r = normalize_source("   ")
        assert r.changed is False
        assert r.warnings == ["Document is empty"]

    def test_force_reclassifies_clean_fountain(self):
        r = normalize_source(CLEAN_SCRIPT, force=True)
        assert r.fountain.strip() == CLEAN_SCRIPT.strip()

    def test_loose_heading_gets_canonical_dots(self):
        r = normalize_source("INT LOFT - NIGHT\n\nDust motes.\n")
        assert "INT. LOFT - NIGHT" in r.fountain

    def test_forced_markers_survive(self):
        r = normalize_source(".THE END — KIND OF\n\n@MYSTERY MAN\nHello?\n", force=True)
        assert ".THE END — KIND OF" in r.fountain
        assert "@MYSTERY MAN" in r.fountain


class TestLint:
    def test_flags_lowercase_heading_and_missing_blank(self):
        issues = lint_fountain("INT. LOFT - NIGHT\nSARAH\nHello?\n")
        msgs = [i["message"] for i in issues]
        assert any("blank line" in m for m in msgs)

    def test_clean_script_no_blank_line_issues(self):
        issues = lint_fountain(CLEAN_SCRIPT)
        assert not [i for i in issues if "blank line" in i["message"].lower()]

    def test_flags_cue_split_from_dialogue_by_blank_line(self):
        issues = lint_fountain("INT. LOFT - NIGHT\n\nJOHN\n\nHello?\n")
        assert any("cue and dialogue" in i["message"] for i in issues)


class TestBlankLineNoise:
    """PDF/plain-text dumps often separate EVERY visual line with a blank line."""

    BLANKY = """SMOKE RISING

Written by Jane Doe

12.

INT. DINER - NIGHT

Rain hammers the window. JOE sits

alone, stirring cold coffee.

JOHN

(bitter)

You shouldn't have

come back.

JOE

I never left.

CUT TO:

EXT. STREET - CONTINUOUS

Empty road. Just rain.

2.
"""

    def test_action_paragraphs_not_sliced(self):
        r = normalize_source(self.BLANKY)
        assert "Rain hammers the window. JOE sits\nalone, stirring cold coffee." in r.fountain
        assert r.stats["action_blocks"] == 3

    def test_dialogue_stays_bound_to_cue(self):
        r = normalize_source(self.BLANKY)
        assert "JOHN\n(bitter)\nYou shouldn't have\ncome back." in r.fountain
        assert r.stats["dialogue_lines"] == 3
        assert r.stats["cues"] == 2

    def test_real_paragraph_breaks_still_split(self):
        r = normalize_source("INT. A - NIGHT\n\nRain stops.\n\nShe leaves.\n")
        assert r.stats["action_blocks"] == 2

    def test_output_passes_through_untouched_on_reupload(self):
        first = normalize_source(self.BLANKY).fountain
        second = normalize_source(first)
        assert second.changed is False
        assert second.warnings == [] or all("page-number" not in w for w in second.warnings)


class TestBeautify:
    def test_collapses_extra_blank_lines(self):
        r = beautify_fountain("INT. LOFT - NIGHT\n\n\n\nDust motes.\n\n\nSARAH\nHello?\n")
        assert "\n\n\n" not in r.fountain
        assert r.changed is True

    def test_preserves_dialogue_block(self):
        r = beautify_fountain(CLEAN_SCRIPT)
        assert "JOHN\nYou shouldn't have come back." in r.fountain


class TestDialogueExit:
    """Action lines glued to dialogue (no blank line) must split off."""

    def test_pronoun_action_after_dialogue_splits(self):
        src = "INT. CAFE - DAY\n\nAMANDA\nI love you.\nHARRY\nI love you, too.\nThey kiss again.\n"
        r = normalize_source(src)
        assert "I love you, too.\n\nThey kiss again." in r.fountain
        assert r.stats["dialogue_lines"] == 2
        assert r.stats["cues"] == 2

    def test_known_name_action_after_dialogue_splits(self):
        src = "INT. CAFE - DAY\n\nAMANDA\nHi.\nAmanda pulls away.\n"
        r = normalize_source(src)
        assert "Hi.\n\nAmanda pulls away." in r.fountain

    def test_spoken_third_person_stays_dialogue(self):
        src = "INT. A - NIGHT\n\nJOE\nThey killed him, Martha.\nHe was my friend.\n"
        r = normalize_source(src, force=True)
        assert "They killed him, Martha.\nHe was my friend." in r.fountain

    def test_lint_flags_action_inside_dialogue(self):
        issues = lint_fountain("INT. A - NIGHT\n\nAMANDA\nI love you.\nThey kiss again.\n")
        assert any("Action line inside dialogue" in i["message"] for i in issues)


class TestPdfArtifacts:
    """Trailing footnote stars, broken ligatures, and wrapped-paragraph blanks."""

    SMOKERAW = """INT. DRIVEWAY - DAY

SALLY
(to Harry) *
You want to drive the first shift?
HARRY
No, no ~- you're there already, you

can start.

Harry looks meaningfully at Amanda.

Then he starts to put his stuff -- a duffel bag, a box

of records -- into the back seat of the car, where

Sally's stuff is, too -- suitcases, stereo speakers, a

guitar, boxes of books, a small TV.
"""

    def test_junk_cue_line_still_splits_dialogue(self):
        r = normalize_source(self.SMOKERAW)
        assert "shift?\n\nHARRY\nNo, no" in r.fountain
        assert r.stats["cues"] == 2
        assert r.stats["dialogue_lines"] == 3

    def test_artifacts_sanitized(self):
        r = normalize_source(self.SMOKERAW)
        assert "(to Harry)" in r.fountain
        assert "*" not in r.fountain
        assert "no --" in r.fountain

    def test_wrapped_action_paragraph_rejoined(self):
        r = normalize_source(self.SMOKERAW)
        assert "a duffel bag, a box\nof records" in r.fountain

    def test_wrapped_dialogue_continuation_rejoined(self):
        r = normalize_source(self.SMOKERAW)
        assert "already, you\ncan start." in r.fountain

    def test_idempotent(self):
        first = normalize_source(self.SMOKERAW).fountain
        assert normalize_source(first).changed is False


class TestFdxConversion:
    def test_fountain_fdx(self):
        f = convert_fdx(FONTS_FDx)
        assert "Title: GREENLIGHT" in f.fountain
        assert "Authors: JANE DOE" in f.fountain
        assert "INT. DINER - NIGHT" in f.fountain
        assert f.stats["scenes"] == 1
        assert f.stats["dialogue_lines"] == 1
        assert f.confidence == 0.95

    def test_final_draft_fdx(self):
        f = convert_fdx(FINAL_DRAFT_FDX)
        assert "INT. OFFICE - DAY" in f.fountain
        assert "CUT TO:" in f.fountain
        assert f.stats["scenes"] == 2
        assert f.stats["cues"] == 1
        assert f.stats["dialogue_lines"] == 1

    def test_bad_xml_raises(self):
        with pytest.raises(FdxError):
            convert_fdx("<html><body>hi</body></html>")
        with pytest.raises(FdxError):
            convert_fdx("not xml at all <<<")

    def test_converted_output_passes_normalizer_passthrough(self):
        f = convert_fdx(FONTS_FDx)
        r = normalize_source(f.fountain)
        assert r.changed is False


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from greenlight.api.app import app

    return TestClient(app)


class TestUploadPipeline:
    @pytest.fixture(autouse=True)
    def _cleanup(self, client):
        self._created: list[str] = []
        yield
        for sid in self._created:
            client.delete(f"/api/scripts/{sid}")

    def _upload(self, client, filename, content: bytes, title="T"):
        res = client.post(
            "/api/scripts/upload",
            files={"file": (filename, content, "text/plain")},
            data={"title": title},
        )
        if res.status_code == 200:
            self._created.append(res.json()["id"])
        return res

    def test_messy_txt_upload_reports_stats_and_normalization(self, client):
        res = self._upload(client, "script.txt", MESSY_SCRIPT.encode())
        assert res.status_code == 200
        data = res.json()
        assert data["source_format"] == "txt"
        assert data["normalized"] is True
        assert data["stats"]["scenes"] == 2
        assert data["loaded"]["scene_count"] == 2
        text = client.get(f"/api/scripts/{data['id']}/text").text
        assert "INT. DINER - NIGHT" in text
        # served text must be the Fountain version, not the raw blob
        assert "\n\nJOHN\n" in text

    def test_clean_fountain_upload_is_untouched(self, client):
        res = self._upload(client, "clean.fountain", CLEAN_SCRIPT.encode())
        data = res.json()
        assert data["normalized"] is False
        assert data["stats"]["scenes"] == 1

    def test_unsupported_extension_rejected(self, client):
        res = self._upload(client, "notes.docx", b"PK\x03\x04junk")
        assert res.status_code == 415

    def test_scanned_pdf_rejected_415(self, client):
        import io

        from pypdf import PdfWriter

        buf = io.BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        writer.write(buf)
        res = self._upload(client, "scan.pdf", buf.getvalue())
        assert res.status_code == 415
        assert "text layer" in res.json()["detail"]

    def test_fdx_upload_converts(self, client):
        res = self._upload(client, "movie.fdx", FONTS_FDx.encode())
        assert res.status_code == 200
        data = res.json()
        assert data["source_format"] == "fdx"
        assert data["stats"]["scenes"] == 1

    def test_normalize_retry_commits_new_version(self, client):
        res = self._upload(client, "script2.txt", MESSY_SCRIPT.encode())
        sid = res.json()["id"]
        repo = client.get(f"/api/scripts/{sid}/repo").json()
        versions_before = len(repo["versions"])

        retry = client.post(f"/api/scripts/{sid}/normalize", json={"force": True})
        assert retry.status_code == 200
        body = retry.json()
        assert body["scene_count"] == 2
        # force-normalize of already-normalized text yields identical content
        assert body["unchanged"] is True
        assert body["version_id"] == repo["versions"][-1]["version_id"]

        repo_after = client.get(f"/api/scripts/{sid}/repo").json()
        assert len(repo_after["versions"]) == versions_before

    def test_normalize_retry_404_for_unknown(self, client):
        res = client.post("/api/scripts/nonexistent-id/normalize", json={})
        assert res.status_code == 404

    def test_beautify_endpoint(self, client):
        res = client.post(
            "/api/screenplay/beautify", json={"text": "INT. LOFT - NIGHT\nSARAH\nHi\n"}
        )
        assert res.status_code == 200
        data = res.json()
        assert "\n\nSARAH\n" in data["text"]
        assert data["changed"] is True
