"""Zip file validation against a stage's build matrix.

Scans a zip file's directory structure and validates that all required
build labels and artifact types are present.

Expected zip structure:
    MFG_BASE/
        build.json
        *.hex
        *.cfw  (if produces_cfw)
    FUT_VERBOSE_A/
        build.json
        *.hex
        *.cfw
"""

import zipfile
from dataclasses import dataclass, field
from typing import IO, Optional


ARTIFACT_EXT_MAP = {
    ".hex": "plaintextHex",
    ".cfw": "encryptedCfw",
    ".json": "manifest",
    ".bin": "other",
    ".log": "log",
    ".zip": "other",
}


@dataclass
class ZipValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    labels_found: list[str] = field(default_factory=list)
    file_count: int = 0


def validate_zip(
    zip_file: IO[bytes],
    build_matrix_entries: list,
) -> ZipValidationResult:
    """Validate a zip file's contents against a stage's build matrix.

    Args:
        zip_file: File-like object containing the zip.
        build_matrix_entries: List of StageBuildMatrix records from the DB.

    Returns:
        ZipValidationResult with valid flag, errors, and warnings.
    """
    result = ZipValidationResult(valid=True)

    try:
        zf = zipfile.ZipFile(zip_file, "r")
    except zipfile.BadZipFile:
        result.valid = False
        result.errors.append("File is not a valid zip archive")
        return result

    # Check for path traversal
    for name in zf.namelist():
        if name.startswith("/") or ".." in name:
            result.valid = False
            result.errors.append(f"Unsafe path in zip: {name}")
            return result

    # Build expected labels from matrix
    required_labels = {entry.label for entry in build_matrix_entries}

    # Scan zip for top-level directories (= labels)
    found_labels: dict[str, list[str]] = {}
    for name in zf.namelist():
        parts = name.split("/")
        if len(parts) < 2 or not parts[0]:
            continue
        label = parts[0]
        filename = parts[-1]
        if filename:  # skip directory entries
            found_labels.setdefault(label, []).append(filename)

    result.labels_found = list(found_labels.keys())
    result.file_count = sum(len(files) for files in found_labels.values())

    # Check required labels
    missing_labels = required_labels - set(found_labels.keys())
    if missing_labels:
        result.valid = False
        for label in sorted(missing_labels):
            result.errors.append(f"Missing required label directory: {label}")

    # Check artifact types per label
    matrix_by_label = {entry.label: entry for entry in build_matrix_entries}
    for label, files in found_labels.items():
        entry = matrix_by_label.get(label)
        if not entry:
            result.warnings.append(f"Extra label directory: {label} (not in build matrix)")
            continue

        exts = {f.rsplit(".", 1)[-1].lower() if "." in f else "" for f in files}

        if entry.producesHex and "hex" not in exts:
            result.valid = False
            result.errors.append(f"{label}: missing .hex file (producesHex=true)")

        if entry.producesCfw and "cfw" not in exts:
            result.valid = False
            result.errors.append(f"{label}: missing .cfw file (producesCfw=true)")

    zf.close()
    return result


def classify_file(filename: str) -> Optional[str]:
    """Map a filename to an artifactType based on extension."""
    for ext, artifact_type in ARTIFACT_EXT_MAP.items():
        if filename.lower().endswith(ext):
            return artifact_type
    return "other"
