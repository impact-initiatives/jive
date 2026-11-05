from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # model_config: SettingsConfigDict = SettingsConfigDict(
    #     env_file=".env",
    #     env_ignore_empty=True,
    #     extra="ignore",
    # )

    MIN_FUZZY_MATCH_SCORE: int = 80
    FUZZY_MATCH_STRING_LENGTH_RATIO: float = 0.7

    # for some validation rules and dynamic model creation
    IGNORE_COLUMNS_FOR_VALIDATION: set[str] = {
        "enum_id",
        "_index",
        "index",
        "_parent_index",
        "parent_index",
        "start",
        "end",
        "audit_url",
        "_id",
        "instance_name",
        "row_index",
    }

    IGNORE_COLUMNS_FOR_MATCHING: set[str] = {
        "enum_id",
        "_index",
        "index",
        "_parent_index",
        "parent_index",
        "start",
        "end",
        "audit_url",
        "instance_name",
        "row_index",
    }

    MIN_COLUMN_MATCHING_OVERLAP: float = 0.85

    ID_FILTER_NAMES: set[str] = {"start", "end"}  # , "_index"

    # these are ordered in preference in case a process using them need
    # to preference them
    COMMON_ID_COLUMN_NAMES: list[str] = ["person_id", "_uuid", "uuid"]  # ,

    # for dynamic model creation
    CLEAN_DATA_SHEET_SEARCH_TERMS: list[str] = ["clean_data"]
    CLEANING_LOG_SHEET_SEARCH_TERMS: list[str] = ["cleaning_log"]
    DELETION_LOG_SHEET_SEARCH_TERMS: list[str] = ["deletion_log"]
    RAW_DATA_SHEET_SEARCH_TERMS: list[str] = ["raw_data"]

    SURVEY_SHEET_NAME: str = "survey"
    CHOICES_SHEET_NAME: str = "choices"

    # for the NaNCheck validator. keep as float
    NANCHECK_NUMERIC_VALUES: list[float] = [-999, -99, 99, 999, -88, -888, 88, 888]
    NANCHECK_STRING_VALUES: list[str] = [
        "-999",
        "-99",
        "99",
        "999",
        "-88",
        "-888",
        "88",
        "888",
    ]
    # min length a number has to be for pii phone number check
    MIN_PHONE_LENGTH: int = 6

    # limits the output of each of the validation results. set below 0 to ignore.
    LIMIT_DETAILS_THRESHOLD: int = -1

    # used in RawToCleanToLogCheck to determine how many columns to process at once
    # useful to reduce memory usage
    COLUMN_CHUNK_SIZE: int = 400

    # for local testing
    # eg Path.cwd() / "dataset_config" / "v2026.06.25.01"
    DATASET_CONFIG_LOCAL_DIR: Path = Path.cwd() / "dataset_config"
    # DATASET_CONFIG_LOCAL_DIR: Path = Path("/home/g-impact/Documents/dev/argus_schemas")
    DATASET_CONFIG_DIR: Path = Path.cwd() / "dataset_config"
    DATASET_CONFIG_URL: str = (
        "https://api.github.com/repos/impact-initiatives/argus_schemas/releases/latest"
    )
    Path(DATASET_CONFIG_DIR).mkdir(parents=True, exist_ok=True)

    FALLBACK_PROGRAMME: str = "other"
    FALLBACK_OUTPUT: str = "dataset"
    FALLBACK_LOCALE: str = "en"

    DATASETS_USING_DYNAMIC_LOADING: list[str] = ["msna_dataset"]


settings = Settings()
