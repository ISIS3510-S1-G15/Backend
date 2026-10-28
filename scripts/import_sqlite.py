import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Boolean, DateTime, JSON, func, inspect, select, text

from app import models
from app.database import Base, engine

ROOT = Path(__file__).resolve().parent.parent


class ImportFailure(Exception):
    pass


def expected_head() -> str:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    return ScriptDirectory.from_config(config).get_current_head()


def require_schema(conn) -> None:
    if not inspect(conn).has_table("alembic_version"):
        raise ImportFailure("El esquema no esta inicializado. Ejecuta: alembic upgrade head")
    current = conn.execute(text("select version_num from alembic_version")).scalar()
    if current != expected_head():
        raise ImportFailure(
            f"El esquema esta en {current} y se esperaba {expected_head()}. Ejecuta: alembic upgrade head"
        )


def convert(column, value):
    if value is None:
        return None
    if isinstance(column.type, DateTime):
        moment = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
        if column.type.timezone:
            return moment.replace(tzinfo=timezone.utc) if moment.tzinfo is None else moment.astimezone(timezone.utc)
        return moment.astimezone(timezone.utc).replace(tzinfo=None) if moment.tzinfo else moment
    if isinstance(column.type, Boolean):
        return bool(value)
    if isinstance(column.type, JSON):
        return json.loads(value) if isinstance(value, (str, bytes)) else value
    return value


def read_sqlite(src: sqlite3.Connection, table):
    present = src.execute(
        "select 1 from sqlite_master where type = 'table' and name = ?", (table.name,)
    ).fetchone()
    if not present:
        return None
    cursor = src.execute(f'select * from "{table.name}"')
    names = [d[0] for d in cursor.description]
    unknown = set(names) - set(table.columns.keys())
    if unknown:
        raise ImportFailure(f"La tabla {table.name} tiene columnas desconocidas en SQLite: {sorted(unknown)}")
    return [{n: convert(table.columns[n], v) for n, v in zip(names, row)} for row in cursor.fetchall()]


def key_of(table, row):
    return tuple(row[c.name] for c in table.primary_key.columns)


def serial_column(table):
    pk = list(table.primary_key.columns)
    if len(pk) == 1 and pk[0].autoincrement and not pk[0].foreign_keys and pk[0].type.python_type is int:
        return pk[0]
    return None


def target_counts(conn, tables) -> dict:
    return {t.name: conn.execute(select(func.count()).select_from(t)).scalar() for t in tables}


def fix_sequences(conn, tables) -> None:
    for table in tables:
        column = serial_column(table)
        if column is None:
            continue
        name = column.name
        conn.execute(text(
            f"select setval(pg_get_serial_sequence('{table.name}', '{name}'), "
            f"coalesce((select max({name}) from {table.name}), 1), "
            f"(select max({name}) from {table.name}) is not null)"
        ))


def orphan_count(conn, table) -> int:
    total = 0
    for fk in table.foreign_keys:
        child, parent = fk.parent, fk.column
        query = (
            select(func.count())
            .select_from(table.outerjoin(parent.table, child == parent))
            .where(child.is_not(None), parent.is_(None))
        )
        total += conn.execute(query).scalar()
    return total


def validate(conn, src_data: dict, tables, report: list) -> list:
    problems = []
    for table in tables:
        rows = src_data.get(table.name)
        expected = len(rows) if rows is not None else 0
        loaded = conn.execute(select(func.count()).select_from(table)).scalar()
        if expected != loaded:
            problems.append(f"{table.name}: SQLite={expected} PostgreSQL={loaded}")
        if rows:
            stored = {key_of(table, dict(r._mapping)): dict(r._mapping) for r in conn.execute(select(table))}
            if set(stored) != {key_of(table, r) for r in rows}:
                problems.append(f"{table.name}: las llaves primarias no coinciden")
            else:
                for row in rows:
                    if stored[key_of(table, row)] != row:
                        problems.append(f"{table.name}: la fila {key_of(table, row)} difiere entre SQLite y PostgreSQL")
                        break
        orphans = orphan_count(conn, table)
        if orphans:
            problems.append(f"{table.name}: {orphans} filas con llave foranea huerfana")
        report.append(f"{table.name:<24} SQLite={expected:<6} PostgreSQL={loaded:<6} huerfanas={orphans}")

    users = conn.execute(
        select(func.count(), func.count(func.distinct(models.User.email))).select_from(models.User)
    ).one()
    if users[0] != users[1]:
        problems.append("users: correos duplicados")

    for table in tables:
        column = serial_column(table)
        if column is None:
            continue
        sequence = conn.execute(text(f"select pg_get_serial_sequence('{table.name}', '{column.name}')")).scalar()
        last = conn.execute(text(f"select last_value from {sequence}")).scalar()
        top = conn.execute(select(func.max(column))).scalar()
        if top is not None and last < top:
            problems.append(f"{table.name}: la secuencia ({last}) esta por debajo del maximo id ({top})")
    return problems


def run(sqlite_path: Path, verify_only: bool) -> int:
    uri = f"file:{sqlite_path.resolve().as_posix()}?mode=ro"
    src = sqlite3.connect(uri, uri=True)
    tables = list(Base.metadata.sorted_tables)
    report: list = []
    try:
        data = {t.name: read_sqlite(src, t) for t in tables}
    finally:
        src.close()

    with engine.connect() as probe:
        require_schema(probe)

    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            if not verify_only:
                filled = {n: c for n, c in target_counts(conn, tables).items() if c}
                if filled:
                    raise ImportFailure(
                        "La base PostgreSQL ya contiene datos, no se importa nada: "
                        + ", ".join(f"{n}={c}" for n, c in filled.items())
                    )
                for table in tables:
                    rows = data[table.name]
                    if rows:
                        conn.execute(table.insert(), rows)
                fix_sequences(conn, tables)
            problems = validate(conn, data, tables, report)
            if problems:
                raise ImportFailure("Discrepancias detectadas:\n  " + "\n  ".join(problems))
            if verify_only:
                transaction.rollback()
            else:
                transaction.commit()
        except Exception:
            transaction.rollback()
            raise

    print("\n".join(report))
    print("VERIFICACION OK" if verify_only else "IMPORTACION OK")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Importa campus_eats.db (SQLite) a PostgreSQL")
    parser.add_argument("sqlite_path", type=Path)
    parser.add_argument("--verify", action="store_true", help="solo compara SQLite con PostgreSQL, sin importar")
    args = parser.parse_args(argv)
    if not args.sqlite_path.is_file():
        print(f"ERROR: no existe {args.sqlite_path}", file=sys.stderr)
        return 2
    try:
        return run(args.sqlite_path, args.verify)
    except ImportFailure as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
