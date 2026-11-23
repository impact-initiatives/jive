from pathlib import Path

import yaml


def load_file(file_path: str | Path):
    """
    Loads a yaml file and its definitions. Supports imports from multiple files
    at the top level

    Limitations
    - nested imports are not processed: if file1.yml  imports file2.yml which imports
    file3.yml, file3.yml will not be processed. This can be added if required

    """

    seen_paths = set()

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"YAML configuration file not found: {path}")

    seen_paths.add(str(path))

    base_dir = path.parent

    try:
        with open(path, encoding="utf-8") as f:
            raw_data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML syntax in {file_path}: {e}") from e

    if not isinstance(raw_data, dict):
        raise ValueError("YAML root must be a dictionary.")

    # 1. Load Import Definitions
    definitions: dict[str, str] = {}
    imports: list[str] = raw_data.pop("_imports", [])

    for imp_path in imports:
        full_path = base_dir / imp_path
        if not full_path.exists():
            raise FileNotFoundError(f"Imported component file not found: {full_path}")

        # check for recursive imports
        if full_path in seen_paths:
            raise ValueError(f"Circular import detected: {full_path}")
        seen_paths.add(str(full_path))

        with open(full_path, encoding="utf-8") as f:
            comp_data = yaml.safe_load(f)

        if not isinstance(comp_data, dict) or "definitions" not in comp_data:
            raise ValueError(f"Component file {imp_path} must contain a 'definitions' key.")

        # check for duplicate definitions between imports
        imported_defs: dict[str, str] = comp_data["definitions"]
        duplicates = set(definitions.keys()) & set(imported_defs.keys())
        if duplicates:
            raise ValueError(
                f"Duplicate definitions from {imp_path}: {sorted(duplicates)}. "
                f"This would cause silent overwrites."
            )

        definitions.update(comp_data["definitions"])

    return raw_data, definitions
