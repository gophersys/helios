import atexit
import os
from pathlib import Path
from typing import Optional, Literal

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func
from sshtunnel import SSHTunnelForwarder

from corekinect.utils import EnvConfig
from corekinect.utils import SingletonThreadSafeMeta


class SSHConfig(EnvConfig):
    ENV_PREFIX = "SSH_"

    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None  # ssh password OR key passphrase (older sshtunnel)
    pkey_path: Optional[Path] = None  # OpenSSH private key path
    pkey_passphrase: Optional[str] = None
    remote_bind_host: Optional[str] = None
    remote_bind_port: Optional[int] = None
    local_bind_host: Optional[str] = None
    local_bind_port: Optional[int] = None  # leave at 0 to auto-assign
    allow_agent: Optional[bool] = None


class DBConfig(EnvConfig):
    ENV_PREFIX = "DB_"

    # Either provide URI or components:
    uri: Optional[str] = None
    driver: str = "postgresql+psycopg2"
    username: Optional[str] = None
    password: Optional[str] = None
    pkey_path: Optional[Path] = None
    host: str = "127.0.0.1"
    port: int = 5432
    database_name: Optional[str] = None
    connect_timeout: int = 5
    echo: bool = False


def _apply_namespace_env(ns: Optional[Literal["VAL_1_0", "DEV_1_0", "DEV_0_9"]]) -> None:
    """
    If ns is provided, copies env vars like:
        VAL_1_0_DB_DRIVER -> DB_DRIVER
        VAL_1_0_SSH_HOST -> SSH_HOST
    into process env so DBConfig/SSHConfig can read them with their static prefixes.
    """
    if not ns:
        return
    ns = ns.rstrip("_") + "_"  # ensure exactly one trailing underscore

    # Map of {plain_key: [namespaced_aliases...]} in priority order
    db_map = {
        "DB_URI": [f"{ns}DB_URI"],
        "DB_DRIVER": [f"{ns}DB_DRIVER"],
        "DB_USERNAME": [f"{ns}DB_USERNAME", f"{ns}DB_USER"],
        "DB_PASSWORD": [f"{ns}DB_PASSWORD", f"{ns}DB_PASS"],
        "DB_HOST": [f"{ns}DB_HOST"],
        "DB_PORT": [f"{ns}DB_PORT"],
        "DB_DATABASE_NAME": [f"{ns}DB_DATABASE_NAME", f"{ns}DB_NAME"],
        "DB_CONNECT_TIMEOUT": [f"{ns}DB_CONNECT_TIMEOUT"],
        "DB_ECHO": [f"{ns}DB_ECHO"],
    }
    ssh_map = {
        "SSH_HOST": [f"{ns}SSH_HOST"],
        "SSH_PORT": [f"{ns}SSH_PORT"],
        "SSH_USERNAME": [f"{ns}SSH_USERNAME", f"{ns}SSH_USER"],
        "SSH_PASSWORD": [f"{ns}SSH_PASSWORD"],
        "SSH_PKEY_PATH": [f"{ns}SSH_PKEY_PATH"],
        "SSH_PKEY_PASSPHRASE": [f"{ns}SSH_PKEY_PASSPHRASE"],
        "SSH_REMOTE_BIND_HOST": [f"{ns}SSH_REMOTE_HOST", f"{ns}SSH_REMOTE_BIND_HOST"],
        "SSH_REMOTE_BIND_PORT": [f"{ns}SSH_REMOTE_PORT", f"{ns}SSH_REMOTE_BIND_PORT"],
        "SSH_LOCAL_BIND_HOST": [f"{ns}SSH_LOCAL_HOST", f"{ns}SSH_LOCAL_BIND_HOST"],
        "SSH_LOCAL_BIND_PORT": [f"{ns}SSH_LOCAL_PORT", f"{ns}SSH_LOCAL_BIND_PORT"],
        "SSH_ALLOW_AGENT": [f"{ns}SSH_ALLOW_AGENT"],
    }

    def copy_first_present(target_key: str, candidates: list[str]) -> None:
        for c in candidates:
            v = os.getenv(c)
            if v is not None and v != "":
                os.environ[target_key] = v
                return

    for k, cands in db_map.items():
        copy_first_present(k, cands)
    for k, cands in ssh_map.items():
        copy_first_present(k, cands)


class CoreCloudDBInterface(metaclass=SingletonThreadSafeMeta):
    """
    Context-managed DB interface with an optional SSH tunnel.
    If no settings are provided, reads from environment/.env by default.

    Attributes:
        db (optional[DBConfig]): Database configuration.
        ssh (optional[SSHConfig]): SSH tunnel configuration.
        env (optional[str]): Environment namespace for DB and SSH settings.
        test_query (optional[str]): Query to test the database connection.

    Example:
        with CoreCloudInterface(env_namespace="VAL_1_0") as db:
            db.execute(text("SELECT 1"))
    """

    def __init__(
        self,
        db: Optional[DBConfig] = None,
        ssh: Optional[SSHConfig] = None,
        env: Optional[Literal["VAL_1_0", "DEV_1_0", "DEV_0_9"]] = "VAL_1_0",
        *,
        test_query: Optional[str] = "SELECT 1",
    ):
        self._depth = 0

        load_dotenv(override=False)
        _apply_namespace_env(env)

        self.db = db or DBConfig(namespace=env)
        self.ssh = ssh or SSHConfig(namespace=env)
        self.test_query = test_query

        self.tunnel: Optional[SSHTunnelForwarder] = None
        self.engine = None
        self.Session = None
        self.session = None

        self.passed_session_test = False

        # Clean up on exit
        if not hasattr(self, "_atexit_reg"):
            atexit.register(self._teardown)
            self._atexit_reg = True

    def __enter__(self):
        # Reentry guard
        if self._depth > 0:
            self._depth += 1
            return self.session

        self._depth = 1

        try:
            # Start SSH tunnel if configured
            if self.ssh.host:
                kwargs = dict(
                    ssh_address_or_host=(self.ssh.host, self.ssh.port),
                    ssh_username=self.ssh.username,
                    remote_bind_address=(self.ssh.remote_bind_host, self.ssh.remote_bind_port),
                    local_bind_address=(self.ssh.local_bind_host, self.ssh.local_bind_port),
                    allow_agent=self.ssh.allow_agent,
                )
                if self.ssh.password:
                    kwargs["ssh_password"] = self.ssh.password
                if self.ssh.pkey_path:
                    kwargs["ssh_pkey"] = str(self.ssh.pkey_path)
                if self.ssh.pkey_passphrase:
                    kwargs["ssh_private_key_password"] = self.ssh.pkey_passphrase

                self.tunnel = SSHTunnelForwarder(**kwargs)
                self.tunnel.start()
                local_host = self.ssh.local_bind_host
                local_port = self.tunnel.local_bind_port
            else:
                local_host = self.db.host
                local_port = self.db.port

            # Build URI
            if self.db.uri:
                url = make_url(self.db.uri)
                if self.tunnel:
                    url = url.set(host=local_host, port=local_port)
                q = dict(url.query) if url.query else {}
                q.setdefault("connect_timeout", str(self.db.connect_timeout))
                url = url.set(query=q)
            else:
                url = URL.create(
                    drivername=self.db.driver,
                    username=self.db.username,
                    password=self.db.password,
                    host=local_host,
                    port=local_port,
                    database=self.db.database_name,
                    query={"connect_timeout": str(self.db.connect_timeout)},
                )

            # Open session using engine
            self.engine = create_engine(url, pool_pre_ping=True, future=True, echo=self.db.echo)
            self.Session = sessionmaker(bind=self.engine)
            self.session = self.Session()

            # Test connection
            if self.test_query:
                try:
                    self.session.execute(text(self.test_query))
                    self.passed_session_test = True
                except SQLAlchemyError as e:
                    self._teardown()
                    raise ConnectionError(f"Database connection failed: {e}") from e

            return self.session

        except Exception:
            self._depth = 0
            self._teardown()
            raise

    def __exit__(self, exc_type, exc_value, traceback):
        if self._depth <= 1:
            self._teardown()
            self._depth = 0
        else:
            self._depth -= 1
        return False

    def _teardown(self):
        if self.session:
            try:
                self.session.close()
            finally:
                self.session = None
        if self.engine:
            try:
                self.engine.dispose()
            finally:
                self.engine = None
        if self.tunnel:
            try:
                self.tunnel.stop()
            finally:
                self.tunnel = None

    def close(self):
        """
        Close the session and tunnel explicitly.
        This is optional since __exit__ will handle it, but can be used for manual cleanup.
        """
        self._teardown()

    @classmethod
    def reset_singleton(cls, env: str | None = None) -> None:
        store = getattr(type(cls), "_instances", {})
        key = (cls, env) if env is not None else cls
        inst = store.pop(key, None)
        if inst:
            inst.close()

    @staticmethod
    def device_time_expr(model, field_names):
        """
        Accepts a string (single column) or a sequence of strings.
        Returns the ORM column or COALESCE(...) of columns.
        """
        if isinstance(field_names, str):
            return getattr(model, field_names)

        if not field_names:
            raise ValueError("device_time_expr: field_names must be non-empty")

        cols = [getattr(model, name) for name in field_names]
        return cols[0] if len(cols) == 1 else func.coalesce(*cols)


def _run_codegen(conn_str, out_file):
    import sys, subprocess

    with open(out_file, "w", encoding="utf-8") as f:
        subprocess.run(
            [sys.executable, "-m", "sqlacodegen", conn_str],
            check=True,
            stdout=f,
        )


def _update_cc_test_data_v0p9_orm():
    load_dotenv(override=False)
    _apply_namespace_env("DEV_0_9")
    db = DBConfig(namespace="DEV_0_9")
    _run_codegen(f"{db.driver}://{db.username}:{db.password}@{db.host}:{db.port}/{db.database_name}", "db_orm_v0_9.py")


def _update_cc_test_data_v1p0_orm():
    load_dotenv(override=False)
    _apply_namespace_env("VAL_1_0")
    db = DBConfig(namespace="VAL_1_0")
    _run_codegen(f"{db.driver}://{db.username}:{db.password}@{db.host}:{db.port}/{db.database_name}", "db_orm_v1_0.py")


if __name__ == "__main__":
    _update_cc_test_data_v0p9_orm()
    _update_cc_test_data_v1p0_orm()
