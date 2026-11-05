import zipfile
from pathlib import Path

import httpx2
import yaml
from httpx2 import Response

from ..config import settings


def download_config(download_dir: str | Path = "dataset_config"):
    """
    Downloads the latest release, extracts it if necessary,
    filters only .yaml files, and preserves directory structure.
    Also lowers all folders and file names.
    """

    # Setup Download Directory
    base_path = Path(download_dir)
    base_path.mkdir(parents=True, exist_ok=True)

    try:
        response: Response = httpx2.get(settings.DATASET_CONFIG_URL)
        response.raise_for_status()
        release_data = response.json()
    except Exception as e:
        raise RuntimeError(f"Error getting latest dataset config release: {e}") from None

    tag_name = release_data["tag_name"]

    # Check if this version has already been processed
    versioned_target: Path = base_path / tag_name
    if versioned_target.exists():
        yaml_files = list(versioned_target.rglob("*.yaml")) + list(versioned_target.rglob("*.yml"))
        if len(yaml_files) > 0:
            return versioned_target

    archive_name = f"{release_data.get('name', tag_name)}.zip"
    archive_path = base_path / f"_temp_{archive_name}"

    # Stream download
    try:
        with httpx2.stream("GET", release_data["zipball_url"], follow_redirects=True) as response:
            response.raise_for_status()
            with open(archive_path, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=8192):
                    f.write(chunk)
    except Exception as e:
        raise RuntimeError(f"Error downloading latest dataset release zip file: {e}") from None

    try:
        versioned_target.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(archive_path, "r") as zip_ref:
            namelist = zip_ref.namelist()

            for file_info in namelist:
                # Prevent path traversal attacks using the original path string
                dest_original = versioned_target / file_info
                try:
                    _ = dest_original.resolve().relative_to(versioned_target.resolve())
                except ValueError:
                    # Skip paths that escape the target directory (e.g., "../../../etc/passwd")
                    continue

                target_rel_path = Path(file_info.lower())

                # Strip the GitHub root folder (e.g., "owner-repo-hash/")
                parts = target_rel_path.parts

                # GitHub archives usually have one root folder.
                # Check if there are parts left after stripping the first one
                if len(parts) > 1:
                    target_rel_path = Path(*parts[1:])
                else:
                    # If stripping leaves an empty path or just the file in root, handle accordingly
                    # If the file was directly in root (rare for GitHub zips but possible), keep it
                    # If parts == ('',) or similar, skip
                    if not str(target_rel_path).strip():
                        continue
                    # Otherwise, use the single part (file) directly
                    # No need to re-construct Path here if it's just a filename

                dest_file = versioned_target / target_rel_path
                dest_file.parent.mkdir(parents=True, exist_ok=True)

                if dest_file.suffix.lower() in (".yaml", ".yml"):
                    # Extract content
                    with zip_ref.open(file_info) as source, open(dest_file, "wb") as target:
                        _ = target.write(source.read())
                else:
                    pass

    except Exception as e:
        raise RuntimeError(f"Error extracting zip files: {e}") from None
    finally:
        # Cleanup temporary archive
        if archive_path.exists():
            archive_path.unlink()

    return versioned_target


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
