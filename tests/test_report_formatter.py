import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from report_formatter import format_comment_adf


def _make_response(success: bool, errors=None, warnings=None, passed=None):
    """Helper to build a minimal PipelineResponse-like object for testing."""
    from unittest.mock import MagicMock

    response = MagicMock()
    response.success = success

    # Mock metadata
    response.metadata.dataset_type = "jmmi"
    response.metadata.timestamp = "2023-01-01T12:00:00Z"

    # Lists of dicts for the new formatter
    response.errors = errors if errors else []
    response.warnings = warnings if warnings else []
    response.admin_errors = []
    response.passed = passed if passed else []

    return response


class TestFormatCommentAdf:
    """Tests for the ADF report formatter."""

    def _get_all_text(self, node: dict) -> str:
        """Helper to recursively extract all text runs from an ADF node."""
        if "text" in node:
            return node["text"]
        text_runs = []
        if "content" in node:
            for child in node["content"]:
                text_runs.append(self._get_all_text(child))
        return " ".join(text_runs)

    def test_passing_response_structure(self):
        response = _make_response(success=True)
        adf = format_comment_adf("RQA-123", response)

        assert adf["version"] == 1
        assert adf["type"] == "doc"
        assert isinstance(adf["content"], list)
        assert len(adf["content"]) >= 3  # Panel (status), Panel (note), Rule/Footer

    def test_passing_response_contains_passed_text(self):
        response = _make_response(success=True)
        adf = format_comment_adf("RQA-123", response)

        heading = adf["content"][0]
        heading_text = heading["content"][0]["content"][0]["text"]
        assert "PASSED" in heading_text

    def test_failing_response_contains_failed_text(self):
        response = _make_response(success=False, errors=[{"rule": "Mandatory"}])
        adf = format_comment_adf("RQA-123", response)

        heading = adf["content"][0]
        heading_text = heading["content"][0]["content"][0]["text"]
        assert "FAILED" in heading_text

    def test_failing_response_mentions_attachment(self):
        response = _make_response(success=False, errors=[{"rule": "Mandatory"}])
        adf = format_comment_adf("RQA-123", response)

        full_text = self._get_all_text(adf)
        assert (
            "report" in full_text.lower()
            or "attachment" in full_text.lower()
            or "excel" in full_text.lower()
        )

    def test_passing_response_mentions_ready(self):
        response = _make_response(success=True)
        adf = format_comment_adf("RQA-123", response)

        full_text = self._get_all_text(adf)
        assert (
            "no further action" in full_text.lower()
            or "ready" in full_text.lower()
            or "meets" in full_text.lower()
        )

    def test_dataset_type_displayed(self):
        response = _make_response(success=True)
        adf = format_comment_adf("RQA-123", response)

        full_text = self._get_all_text(adf)
        assert "jmmi" in full_text.lower()

    def test_table_generated_for_errors(self):
        response = _make_response(
            success=False,
            errors=[{"rule": "Mandatory"}, {"rule": "Mandatory"}],
            warnings=[{"rule": "MissingSheet"}],
        )
        adf = format_comment_adf("RQA-123", response)

        # Panel (0), Panel (1), Paragraph (2), Table (3), etc.
        table = adf["content"][3]
        assert table["type"] == "table"

        # Header + 2 unique rules (Mandatory, MissingSheet)
        assert len(table["content"]) == 3

        # First row after header is Mandatory, with count 2
        first_rule_row = table["content"][1]
        cells = first_rule_row["content"]
        assert "Mandatory" in cells[0]["content"][0]["content"][0]["text"]
        assert "2" in cells[2]["content"][0]["content"][0]["text"]

    def test_passed_checks_listed_in_note(self):
        response = _make_response(
            success=True, passed=[{"rule": "DuplicateSheetMatches"}, {"rule": "UniqueColumn"}]
        )
        adf = format_comment_adf("RQA-123", response)

        full_text = self._get_all_text(adf)
        assert "2 core quality checks passed" in full_text or "2 checks passed" in full_text
        assert "DuplicateSheetMatches" in full_text
        assert "UniqueColumn" in full_text

    def test_adf_has_required_keys(self):
        response = _make_response(success=True)
        adf = format_comment_adf("RQA-123", response)

        assert "version" in adf
        assert "type" in adf
        assert "content" in adf
