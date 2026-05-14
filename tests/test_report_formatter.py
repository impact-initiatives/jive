import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from report_formatter import format_comment_adf


def _make_response(success: bool, errors=None, warnings=None, passed=None):
    """Helper to build a minimal PipelineResponse-like object for testing."""
    from unittest.mock import MagicMock

    response = MagicMock()
    response.success = success
    
    #Mock metadata
    response.metadata.dataset_type = "jmmi"
    response.metadata.timestamp = "2023-01-01T12:00:00Z"
    
    #Lists of dicts for the new formatter
    response.errors = errors if errors else []
    response.warnings = warnings if warnings else []
    response.admin_errors = []
    response.passed = passed if passed else []
    
    return response


class TestFormatCommentAdf:
    """Tests for the ADF report formatter."""

    def test_passing_response_structure(self):
        response = _make_response(success=True)
        adf = format_comment_adf(response)

        assert adf["version"] == 1
        assert adf["type"] == "doc"
        assert isinstance(adf["content"], list)
        assert len(adf["content"]) >= 3  # Heading, Dataset Type, Note

    def test_passing_response_contains_passed_text(self):
        response = _make_response(success=True)
        adf = format_comment_adf(response)

        heading = adf["content"][0]
        heading_text = heading["content"][0]["text"]
        assert "PASSED" in heading_text

    def test_failing_response_contains_failed_text(self):
        response = _make_response(success=False, errors=[{"rule": "Mandatory"}])
        adf = format_comment_adf(response)

        heading = adf["content"][0]
        heading_text = heading["content"][0]["text"]
        assert "FAILED" in heading_text

    def test_failing_response_mentions_attachment(self):
        response = _make_response(success=False, errors=[{"rule": "Mandatory"}])
        adf = format_comment_adf(response)

        last_paragraph = adf["content"][-1]
        last_text = last_paragraph["content"][0]["text"]
        assert "Excel" in last_text or "attached" in last_text.lower()

    def test_passing_response_mentions_ready(self):
        response = _make_response(success=True)
        adf = format_comment_adf(response)

        last_paragraph = adf["content"][-1]
        last_text = last_paragraph["content"][0]["text"]
        assert "ready" in last_text.lower() or "meets" in last_text.lower()

    def test_dataset_type_displayed(self):
        response = _make_response(success=True)
        adf = format_comment_adf(response)

        dataset_paragraph = adf["content"][1]
        full_text = " ".join(node["text"] for node in dataset_paragraph["content"])
        assert "jmmi" in full_text.lower()

    def test_table_generated_for_errors(self):
        response = _make_response(
            success=False, 
            errors=[{"rule": "Mandatory"}, {"rule": "Mandatory"}], 
            warnings=[{"rule": "MissingSheet"}]
        )
        adf = format_comment_adf(response)
        
        # Heading (0), Dataset Type (1), Table (2), Note (3)
        assert len(adf["content"]) == 4
        
        table = adf["content"][2]
        assert table["type"] == "table"
        
        # Header + 2 rules
        assert len(table["content"]) == 3 
        
        # First row after header is Mandatory, with count 2
        first_rule_row = table["content"][1]
        cells = first_rule_row["content"]
        assert "Mandatory" in cells[0]["content"][0]["content"][0]["text"]
        assert "2" in cells[2]["content"][0]["content"][0]["text"]

    def test_passed_checks_listed_in_note(self):
        response = _make_response(
            success=True, 
            passed=[{"rule": "DuplicateSheetMatches"}, {"rule": "UniqueColumn"}]
        )
        adf = format_comment_adf(response)
        
        last_paragraph = adf["content"][-1]
        last_text = last_paragraph["content"][0]["text"]
        
        assert "2 checks passed successfully" in last_text
        assert "DuplicateSheetMatches" in last_text
        assert "UniqueColumn" in last_text

    def test_adf_has_required_keys(self):
        response = _make_response(success=True)
        adf = format_comment_adf(response)

        assert "version" in adf
        assert "type" in adf
        assert "content" in adf
