import sqlite3
from contextlib import closing
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory


def migrate(engine, path: Path):
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parent.parent / "migrations"))
    head = ScriptDirectory.from_config(config).get_current_head()
    # SQLite backup includes committed WAL state; never overwrite the original database.
    if path.is_file():
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as source:
            version_table = source.execute(
                "SELECT name FROM sqlite_master WHERE name='alembic_version'").fetchone()
            revision = source.execute("SELECT version_num FROM alembic_version").fetchone() if version_table else None
            if revision and revision[0] != head:
                backups = path.parent / "backups"
                backups.mkdir(exist_ok=True)
                backup = backups / f"study-before-{head}-{uuid4().hex}.db"
                with closing(sqlite3.connect(backup)) as target:
                    source.backup(target)
                    if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                        raise RuntimeError("Migration backup failed integrity check")
    with engine.begin() as connection:
        # sqlite3's legacy transaction mode does not begin transactions for DDL.
        connection.exec_driver_sql("BEGIN")
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
