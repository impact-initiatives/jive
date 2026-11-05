from pathlib import Path

import pytest

from src.argus.orchestrator.validation_pipeline import ValidationPipeline

# TODO Change this to mock the various pipeline components
# otherwise schema changes can make these tests fail


@pytest.fixture
def run_pipeline():
    return ValidationPipeline()


@pytest.fixture
def valid_file():
    return Path("src/tests/loader/jmmi_valid.xlsx")


@pytest.fixture
def invalid_file():
    return Path("src/tests/loader/jmmi_invalid.xlsx")


@pytest.fixture
def valid_file_fuzzy():
    return Path("src/tests/loader/jmmi_valid_fuzzy.xlsx")


@pytest.fixture
def invalid_file_fuzzy():
    return Path("src/tests/loader/jmmi_invalid_fuzzy.xlsx")


@pytest.fixture
def file_not_found():
    return Path("src/tests/loader/not_here.xlsx")


class TestOrchestrator:
    def test_valid_file_jmmi(self, run_pipeline: ValidationPipeline, valid_file: Path):
        results = run_pipeline.run_all(valid_file, "jmmi", "dataset")
        # assert len (results['error']) == 0
        assert len(results["admin_error"]) == 0

    def test_valid_file_other(self, run_pipeline: ValidationPipeline, valid_file: Path):
        results = run_pipeline.run_all(valid_file, "other", "dataset")
        # assert len (results['error']) == 0
        assert len(results["admin_error"]) == 0

    def test_file_not_found(self, run_pipeline: ValidationPipeline, file_not_found: Path):
        results = run_pipeline.run_all(file_not_found, "other", "dataset")
        assert len(results["admin_error"]) == 1

    def test_fuzzy_file(self, run_pipeline: ValidationPipeline, valid_file_fuzzy: Path):
        results = run_pipeline.run_all(valid_file_fuzzy, "jmmi", "dataset")
        assert len(results["admin_error"]) == 0

    def test_invalid_fuzzy_file(self, run_pipeline: ValidationPipeline, invalid_file_fuzzy: Path):
        results = run_pipeline.run_all(invalid_file_fuzzy, "jmmi", "dataset")
        assert len(results["admin_error"]) == 0

    def test_invalid_file_jmmi(self, run_pipeline: ValidationPipeline, invalid_file: Path):
        results = run_pipeline.run_all(invalid_file, "jmmi", "dataset")
        # assert len (results['error']) == 0
        assert len(results["admin_error"]) == 0
