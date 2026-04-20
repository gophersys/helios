"""Regression test for the codegen password-leak fix.

The legacy ``_run_codegen(conn_str, out_file)`` built a connection
string of the form ``driver://user:password@host:port/db`` and passed
it as a CLI argument to ``sqlacodegen``. That string is visible in
``ps``, audit logs, and any process-introspection tooling. The
replacement signature takes a :class:`DBConfig`, builds a password-
free DSN for argv, and threads the password through ``PGPASSWORD``
in the subprocess env.

This test pins the contract so a future refactor can't quietly add
the password back into the argv.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

# ``db_interface`` imports SQLAlchemy at module level; skip the whole
# suite cleanly on dev machines that don't have it (CI / runner image
# install it). The codegen-safety contract is still pinned anywhere
# that does have the dependency.
sqlalchemy = pytest.importorskip("sqlalchemy")

from corekinect.core_cloud.db_interface import DBConfig, _run_codegen  # noqa: E402


def _new_db_config() -> DBConfig:
    """Build a DBConfig without touching the real environment.

    ``DBConfig`` inherits ``EnvConfig`` and would normally read its
    fields from ``DB_*`` env vars. We bypass that to keep the test
    hermetic.
    """
    cfg = DBConfig.__new__(DBConfig)
    cfg.driver = "postgresql+psycopg2"
    cfg.username = "ck_test_user"
    cfg.password = "super-secret-do-not-leak"
    cfg.host = "db.example.local"
    cfg.port = 5432
    cfg.database_name = "concord_test"
    return cfg


def test_run_codegen_does_not_put_password_in_argv(tmp_path) -> None:
    out = tmp_path / "out.py"
    cfg = _new_db_config()

    with patch("subprocess.run") as mock_run:
        _run_codegen(cfg, str(out))

    assert mock_run.called, "subprocess.run should be invoked exactly once"
    call = mock_run.call_args
    argv = call.args[0]
    joined = " ".join(argv)
    assert "super-secret-do-not-leak" not in joined, (
        f"password leaked into subprocess argv: {joined}"
    )
    # Username, host, db name are non-secret and OK in argv.
    assert "ck_test_user" in joined
    assert "db.example.local" in joined


def test_run_codegen_passes_password_via_pgpassword_env(tmp_path) -> None:
    out = tmp_path / "out.py"
    cfg = _new_db_config()

    with patch("subprocess.run") as mock_run:
        _run_codegen(cfg, str(out))

    env = mock_run.call_args.kwargs["env"]
    assert env.get("PGPASSWORD") == "super-secret-do-not-leak", (
        "password must be threaded through PGPASSWORD env var"
    )


def test_run_codegen_raises_when_password_is_empty(tmp_path) -> None:
    cfg = _new_db_config()
    cfg.password = ""
    out = tmp_path / "out.py"

    try:
        _run_codegen(cfg, str(out))
    except ValueError as exc:
        assert "password" in str(exc).lower()
    else:
        raise AssertionError("expected ValueError when DBConfig.password is empty")
