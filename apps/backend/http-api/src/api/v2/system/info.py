from flask import jsonify

from corekinect.utils import collect_build_info
from src.lib.errors import internal_error
from src.lib.types import ApiResponse


def get_system_info():
    """Return build metadata for the running http-api instance."""
    try:
        info = collect_build_info("concord-http-api")
        return jsonify(ApiResponse.ok({
            "service": info.service,
            "version": info.version,
            "environment": info.environment,
            "gitCommit": info.git_commit,
            "gitBranch": info.git_branch,
            "gitDirty": info.git_dirty,
            "buildTime": info.build_time,
            "buildHost": info.build_host,
            "pythonVersion": info.python_version,
            "arch": info.arch,
            "os": info.os_info,
        }).to_dict()), 200
    except Exception as e:
        return internal_error(str(e))
