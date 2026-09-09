"""Tests for the title-page skeleton generator."""

from greenlight.tools.screenplay_template import TITLE_PAGE_SKELETON


class TestTitlePageSkeleton:
    def test_basic_skeleton(self):
        result = TITLE_PAGE_SKELETON("Test Movie", author="John Doe", genre="Drama")
        assert "Title: Test Movie" in result
        assert "Author: John Doe" in result
        assert "Genre: Drama" in result
        assert "Credit: Written by" in result

    def test_empty_author_omitted(self):
        result = TITLE_PAGE_SKELETON("No Author", author="", genre="Comedy")
        lines = result.split("\n")
        assert not any("Author:" in line for line in lines)

    def test_empty_genre_omitted(self):
        result = TITLE_PAGE_SKELETON("No Genre", author="Author", genre="")
        lines = result.split("\n")
        assert not any("Genre:" in line for line in lines)

    def test_draft_date_included(self):
        result = TITLE_PAGE_SKELETON("Drafted", author="Author")
        assert "Draft date: 20" in result

    def test_roundtrip_fountain_parse(self):
        from greenlight.tools.fountain_document import parse_document

        result = TITLE_PAGE_SKELETON("Roundtrip", author="Author")
        elements = parse_document(result)
        title_elements = [e for e in elements if e.type == "title_page"]
        assert len(title_elements) >= 1
        assert any("Roundtrip" in e.text for e in title_elements)

    def test_credit_custom(self):
        result = TITLE_PAGE_SKELETON("My Script", credit="Story by")
        assert "Credit: Story by" in result

    def test_source_omitted_when_empty(self):
        result = TITLE_PAGE_SKELETON("Original", author="Author")
        lines = result.split("\n")
        assert not any("Source:" in line for line in lines)

    def test_source_included(self):
        result = TITLE_PAGE_SKELETON("Adapted", author="Author", source="Based on the novel by X")
        assert "Source: Based on the novel by X" in result

    def test_contact_omitted_when_empty(self):
        result = TITLE_PAGE_SKELETON("No Contact", author="Author")
        lines = result.split("\n")
        assert not any("Contact:" in line for line in lines)

    def test_contact_included(self):
        result = TITLE_PAGE_SKELETON("Contacted", author="Author", contact="me@example.com")
        assert "Contact: me@example.com" in result

    def test_custom_draft_date(self):
        result = TITLE_PAGE_SKELETON("Dated", author="Author", draft_date="2025-01-15")
        assert "Draft date: 2025-01-15" in result
