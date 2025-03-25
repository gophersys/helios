# from packaging.version import InvalidVersion, Version

# from .log import Logger


# def is_version_supported(full_version: str, supported_versions: list[str] | str) -> bool:
#     """
#     Check if a given full version is supported based on a list of supported versions or a single version string.

#     Parameters:
#         full_version (str): The full version to check (e.g., '1.2.331').
#         supported_versions (list[str] or str): A list of supported versions or a single version (e.g., '1.x', ['1.x', '1.2']).

#     Returns:
#         bool: True if the version is supported, False otherwise.

#     Raises:
#         ValueError: If the full version or supported version is invalid.

#     """
#     log = Logger.get_test_case_logger()

#     try:
#         # Parse the full version string
#         parsed_full_version = Version(full_version)
#         log.debug(f"Parsed full version: {parsed_full_version}")
#     except InvalidVersion:
#         log.exception(f"Invalid full version: {full_version}")
#         raise ValueError(f"Invalid full version: {full_version}")

#     # If supported_versions is None or empty, return False
#     if not supported_versions:
#         log.debug("No supported versions specified.")
#         return False

#     # If supported_versions is a string, convert it to a list for uniform processing
#     if isinstance(supported_versions, str):
#         supported_versions = [supported_versions]

#     log.debug(f"Supported versions: {supported_versions}")

#     # Iterate over the supported versions and check if the full version matches
#     for supported in supported_versions:
#         log.debug(f"Checking supported version: {supported}")
#         try:
#             # Handle cases like '1.x' or '2.X' (case-insensitive)
#             if supported.lower().endswith(".x"):
#                 # Extract the major version for comparison
#                 major_version_part = supported.split(".")[0]
#                 major_version = int(major_version_part)
#                 log.debug(f"Major version to compare: {major_version}")
#                 if parsed_full_version.major == major_version:
#                     log.debug(f"Matched major version: {parsed_full_version.major} == {major_version}")
#                     return True
#             else:
#                 # Split the supported version into components
#                 version_parts = supported.split(".")
#                 log.debug(f"Version parts: {version_parts}")

#                 # Extract version numbers
#                 major_version = int(version_parts[0])
#                 minor_version = int(version_parts[1]) if len(version_parts) > 1 else None
#                 micro_version = int(version_parts[2]) if len(version_parts) > 2 else None

#                 log.debug(
#                     f"Supported version components - Major: {major_version}, Minor: {minor_version}, Micro: {micro_version}"
#                 )

#                 # Compare major version
#                 if parsed_full_version.major != major_version:
#                     log.debug(f"Major version mismatch: {parsed_full_version.major} != {major_version}")
#                     continue

#                 # Compare minor version if specified
#                 if minor_version is not None:
#                     if parsed_full_version.minor != minor_version:
#                         log.debug(f"Minor version mismatch: {parsed_full_version.minor} != {minor_version}")
#                         continue

#                 # Compare micro version if specified
#                 if micro_version is not None:
#                     if parsed_full_version.micro != micro_version:
#                         log.debug(f"Micro version mismatch: {parsed_full_version.micro} != {micro_version}")
#                         continue

#                 log.debug("Version matched.")
#                 return True

#         except (InvalidVersion, ValueError) as e:
#             log.exception(f"Invalid supported version: {supported}")
#             raise ValueError(f"Invalid supported version: {supported}") from e

#     # If no match found, return False
#     log.debug(f"No match found for version: {full_version}")
#     return False
