"""One-time, checked copy of the old local SQLite inspection store to PostgreSQL.

The SQLite file and JPEG/PDF evidence are left in place. Refuse a nonempty
target so the audit chain cannot accidentally be merged or duplicated.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
import sqlite3
import sys

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, inspect, select, text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.database import Audit, Inspection, ReportArtifact, database_url


def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)


def ensure_schema():
    engine = create_engine(database_url(), pool_pre_ping=True)
    existing = inspect(engine).get_table_names()
    if not existing:
        config = Config(str(ROOT / 'alembic.ini'))
        command.upgrade(config, 'head')
    elif 'alembic_version' not in existing:
        raise RuntimeError('PostgreSQL has tables without Alembic migration history. Refusing to change it.')
    else:
        config = Config(str(ROOT / 'alembic.ini'))
        command.upgrade(config, 'head')
    return create_engine(database_url(), pool_pre_ping=True)


def migrate(source: Path = ROOT / 'data/oniongrade.db') -> dict:
    source = source.resolve()
    engine = ensure_schema()
    if not source.is_file():
        return {'status': 'no_sqlite_source', 'inspections': 0, 'audit_logs': 0, 'report_artifacts': 0}
    uri = source.as_uri() + '?mode=ro'
    legacy = sqlite3.connect(uri, uri=True)
    legacy.row_factory = sqlite3.Row
    try:
        tables = {row[0] for row in legacy.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        required = {'inspections', 'audit_logs'}
        if not required.issubset(tables):
            raise RuntimeError('SQLite source does not contain the expected inspection and audit tables.')
        inspection_rows = [dict(row) for row in legacy.execute('SELECT * FROM inspections ORDER BY created_at, id')]
        audit_rows = [dict(row) for row in legacy.execute('SELECT * FROM audit_logs ORDER BY id')]
        artifact_rows = [dict(row) for row in legacy.execute('SELECT * FROM report_artifacts')] if 'report_artifacts' in tables else []
        previous = '0' * 64
        for row in audit_rows:
            if row['prev_hash'] != previous or row['hash'] != hashlib.sha256((previous + row['payload']).encode()).hexdigest():
                raise RuntimeError(f"SQLite audit chain is invalid at entry {row['id']}.")
            previous = row['hash']
        for row in inspection_rows:
            record = json.loads(row['payload'])
            stored = record.pop('report_hash')
            if stored != row['report_hash'] or stored != hashlib.sha256(_canonical(record).encode()).hexdigest():
                raise RuntimeError(f"SQLite inspection hash is invalid for {row['id']}.")
        for row in artifact_rows:
            path = source.parent / f"{row['inspection_id']}-report.pdf"
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != row['pdf_sha256']:
                raise RuntimeError(f"Stored PDF evidence is missing or changed for {row['inspection_id']}.")
        with engine.begin() as connection:
            counts = {
                'inspections': connection.scalar(select(func.count()).select_from(Inspection)),
                'audit_logs': connection.scalar(select(func.count()).select_from(Audit)),
                'report_artifacts': connection.scalar(select(func.count()).select_from(ReportArtifact)),
            }
            if any(counts.values()):
                if counts == {'inspections': len(inspection_rows), 'audit_logs': len(audit_rows), 'report_artifacts': len(artifact_rows)}:
                    for row in inspection_rows:
                        stored = connection.scalar(select(Inspection.report_hash).where(Inspection.id == row['id']))
                        if stored != row['report_hash']:
                            raise RuntimeError('PostgreSQL contents differ from the SQLite source. No records were copied.')
                    for row in audit_rows:
                        stored = connection.scalar(select(Audit.hash).where(Audit.id == row['id']))
                        if stored != row['hash']:
                            raise RuntimeError('PostgreSQL audit history differs from the SQLite source.')
                    for row in artifact_rows:
                        stored = connection.scalar(select(ReportArtifact.pdf_sha256).where(ReportArtifact.inspection_id == row['inspection_id']))
                        if stored != row['pdf_sha256']:
                            raise RuntimeError('PostgreSQL PDF hash differs from the SQLite source.')
                    return {'status': 'already_migrated', **counts}
                raise RuntimeError('PostgreSQL contains different data; refusing to merge two audit histories.')
            for row in inspection_rows:
                connection.execute(Inspection.__table__.insert().values(
                    id=row['id'], owner=row['owner'], payload=row['payload'], report_hash=row['report_hash'],
                    created_at=datetime.fromisoformat(row['created_at']),
                ))
            for row in audit_rows:
                connection.execute(Audit.__table__.insert().values(**row))
            if audit_rows:
                connection.execute(text("SELECT setval(pg_get_serial_sequence('audit_logs', 'id'), :last_id)"), {'last_id': max(row['id'] for row in audit_rows)})
            for row in artifact_rows:
                connection.execute(ReportArtifact.__table__.insert().values(**row))
        with engine.connect() as connection:
            actual = {
                'inspections': connection.scalar(select(func.count()).select_from(Inspection)),
                'audit_logs': connection.scalar(select(func.count()).select_from(Audit)),
                'report_artifacts': connection.scalar(select(func.count()).select_from(ReportArtifact)),
            }
        expected = {'inspections': len(inspection_rows), 'audit_logs': len(audit_rows), 'report_artifacts': len(artifact_rows)}
        if actual != expected:
            raise RuntimeError(f'PostgreSQL count verification failed: {actual} vs {expected}.')
        return {'status': 'migrated', **actual}
    finally:
        legacy.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=ROOT / 'data/oniongrade.db')
    args = parser.parse_args()
    print(json.dumps(migrate(args.source), indent=2))
