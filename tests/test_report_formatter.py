import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from report_formatter import format_comment_adf


def _make_response(success: bool, errors: int = 0, warnings: int = 0, info: int = 0):
    """Helper to build a minimal PipelineResponse-like object for testing."""
    from unittest.mock import MagicMock

    response = MagicMock()
    response.success = success
    response.summary.errors = errors
    response.summary.admin_errors = 0
    response.summary.warnings = warnings
    response.summary.info = info
    response.metadata.dataset_type = "jmmi"
    return response


class TestFormatCommentAdf:
    """Tests for the ADF report formatter."""

    def test_passing_response_structure(self):
        response = _make_response(success=True)
        adf = format_comment_adf(response)

        assert adf["version"] == 1
        assert adf["type"] == "doc"
        assert isinstance(adf["content"], list)
        assert len(adf["content"]) >= 3

    def test_passing_response_contains_passed_text(self):
        response = _make_response(success=True)
        adf = format_comment_adf(response)

        heading = adf["content"][0]
        heading_text = heading["content"][0]["text"]
        assert "PASSED" in heading_text

    def test_failing_response_contains_failed_text(self):
        response = _make_response(success=False, errors=5, warnings=2)
        adf = format_comment_adf(response)

        heading = adf["content"][0]
        heading_text = heading["content"][0]["text"]
        assert "FAILED" in heading_text

    def test_failing_response_mentions_attachment(self):
        response = _make_response(success=False, errors=3)
        adf = format_comment_adf(response)

        # The last paragraph should mention the Excel attachment
        last_paragraph = adf["content"][-1]
        last_text = last_paragraph["content"][0]["text"]
        assert "Excel" in last_text or "attached" in last_text.lower()

    def test_passing_response_mentions_ready(self):
        response = _make_response(success=True)
        adf = format_comment_adf(response)

        last_paragraph = adf["content"][-1]
        last_text = last_paragraph["content"][0]["text"]
        assert "ready" in last_text.lower() or "meets" in last_text.lower()

    def test_summary_counts_displayed(self):
        response = _make_response(success=False, errors=7, warnings=3, info=1)
        adf = format_comment_adf(response)

        # The summary paragraph (index 2) should contain the counts
        summary_paragraph = adf["content"][2]
        full_text = " ".join(node["text"] for node in summary_paragraph["content"])
        assert "7" in full_text  # errors + admin_errors
        assert "3" in full_text  # warnings
        assert "1" in full_text  # info

    def test_dataset_type_displayed(self):
        response = _make_response(success=True)
        adf = format_comment_adf(response)

        dataset_paragraph = adf["content"][1]
        full_text = " ".join(node["text"] for node in dataset_paragraph["content"])
        assert "jmmi" in full_text.lower()

    def test_adf_has_required_keys(self):
        response = _make_response(success=True)
        adf = format_comment_adf(response)

        assert "version" in adf
        assert "type" in adf
        assert "content" in adf
