"""Zip file validation against a stage's build matrix.

Scans a zip file's directory structure and validates that all required
build labels and artifact types are present.

Expected zip structure:
    mfg_app_debug/
        build.json
        *.hex
        *.cfw  (if produces_cfw)
    fut_app_base_a/
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
    parsed_version: str | None = None
    version_source: str | None = None


def validate_zip(
    zip_file: IO[bytes],
    build_matrix_entries: list,
    skip_labels: set[str] | None = None,
) -> ZipValidationResult:
    """Validate a zip file's contents against a stage's build matrix.

    Args:
        zip_file: File-like object containing the zip.
        build_matrix_entries: List of StageBuildMatrix records from the DB.
        skip_labels: Labels to exclude from the required check (e.g., modem labels).

    Returns:
        ZipValidationResult with valid flag, errors, and warnings.
    """
    skip_labels = skip_labels or set()
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

    # Check for dangerous file extensions
    BLOCKED_EXTENSIONS = {".exe", ".sh", ".py", ".bat", ".cmd", ".ps1", ".msi", ".dll", ".so"}
    for name in zf.namelist():
        if name.endswith("/"):
            continue  # directory entry
        ext = ("." + name.rsplit(".", 1)[-1].lower()) if "." in name else ""
        if ext in BLOCKED_EXTENSIONS:
            result.valid = False
            result.errors.append(f"Blocked file type: {name} ({ext} files are not allowed)")

    if not result.valid:
        return result

    # Build expected labels from matrix (excluding skipped labels)
    required_labels = {entry.label for entry in build_matrix_entries if entry.label not in skip_labels}

    # Scan zip for top-level directories (= labels)
    # Normalize backslashes (Windows zips) to forward slashes
    all_entries: list[list[str]] = []
    for name in zf.namelist():
        normalized = name.replace("\\", "/")
        parts = [p for p in normalized.split("/") if p]
        if parts:
            all_entries.append(parts)

    # Detect wrapper directory: if all entries share a single root that isn't
    # a known label, strip it and use it as the auto-detected version.
    wrapper_dir = None
    if all_entries:
        roots = {e[0] for e in all_entries if len(e) >= 2}
        if len(roots) == 1:
            candidate = roots.pop()
            if candidate.lower() not in required_labels:
                wrapper_dir = candidate
                # Strip the wrapper from all entries
                all_entries = [e[1:] for e in all_entries if len(e) > 1]
                # Try to extract version from wrapper name
                import re
                ver_match = re.search(r"(\d+\.\d+\.\d+)", candidate)
                if ver_match and not result.parsed_version:
                    result.parsed_version = ver_match.group(1)
                    result.version_source = "zip_wrapper_directory"

    found_labels: dict[str, list[str]] = {}
    for parts in all_entries:
        if len(parts) < 2:
            continue
        label = parts[0]
        filename = parts[-1]
        if filename:
            found_labels.setdefault(label, []).append(filename)

    result.labels_found = list(found_labels.keys())
    result.file_count = sum(len(files) for files in found_labels.values())

    # Check required labels
    missing_labels = required_labels - set(found_labels.keys())
    if missing_labels:
        result.valid = False
        for label in sorted(missing_labels):
            result.errors.append(f"Missing required label directory: {label}")

    # Check for unexpected labels — only allow labels that are in the required set
    extra_labels = set(found_labels.keys()) - required_labels
    if extra_labels:
        # Check if any are skipped modem labels — reject those explicitly
        modem_extras = extra_labels & skip_labels
        other_extras = extra_labels - skip_labels
        for label in sorted(modem_extras):
            result.valid = False
            result.errors.append(f"Zip contains '{label}/' — modem firmware should not be in the zip. Select it from the modem firmware dropdown instead.")
        for label in sorted(other_extras):
            result.valid = False
            result.errors.append(f"Unexpected label directory: {label} (not in build matrix)")

    # Check artifact types per label
    matrix_by_label = {entry.label: entry for entry in build_matrix_entries}
    for label, files in found_labels.items():
        entry = matrix_by_label.get(label)
        if not entry:
            continue  # Already flagged as unexpected above

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
