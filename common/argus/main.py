import argparse
from pathlib import Path

from argus.utils.logging import get_logger
from src.argus.orchestrator.validation_pipeline import ValidationPipeline

logger = get_logger("argus.main")


def main():
    parser = argparse.ArgumentParser(description="Data Validation Framework")
    parser.add_argument("input_file", type=Path, help="Path to Excel file")
    parser.add_argument(
        "--programme_type",
        required=True,
        choices=["jmmi", "other"],
        help="Type of programme.",
    )
    parser.add_argument(
        "--output_type",
        required=True,
        choices=["dataset", "analysis"],
        help="Type of output.",
    )

    args = parser.parse_args()

    pipeline = ValidationPipeline()
    results = pipeline.run_all(
        args.input_file, programme_type=args.programme_type, output_type=args.output_type
    )
    print(results)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception(
            "Error running argus.",
        )

    exit()
