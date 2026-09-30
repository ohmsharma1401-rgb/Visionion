import os
from datetime import datetime, timezone
from sqlalchemy import create_engine, String, Text, DateTime
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass

class Inspection(Base):
    __tablename__ = 'inspections'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner: Mapped[str] = mapped_column(String(100), index=True)
    payload: Mapped[str] = mapped_column(Text())
    report_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

class Audit(Base):
    __tablename__ = 'audit_logs'
    id: Mapped[int] = mapped_column(primary_key=True)
    payload: Mapped[str] = mapped_column(Text())
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))

class ReportArtifact(Base):
    __tablename__ = 'report_artifacts'
    inspection_id: Mapped[str] = mapped_column(String(36),primary_key=True)
    pdf_sha256: Mapped[str] = mapped_column(String(64))

class User(Base):
    __tablename__ = 'users'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

class EmailOtp(Base):
    __tablename__ = 'email_otps'
    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    sent_at: Mapped[datetime] = mapped_column(DateTime)
    attempts: Mapped[int] = mapped_column(default=0)

def database_url() -> URL:
    """Use PostgreSQL in deployment; allow explicit SQLite for local development/tests."""
    supplied = os.getenv('DATABASE_URL')
    if supplied:
        url = make_url(supplied)
        # Managed providers commonly supply postgres:// or postgresql:// URLs.
        # This application installs psycopg 3, not the default psycopg2 driver.
        if url.drivername in ('postgres', 'postgresql'):
            url = url.set(drivername='postgresql+psycopg')
    else:
        required = ('POSTGRES_HOST', 'POSTGRES_PORT', 'POSTGRES_USER', 'POSTGRES_PASSWORD', 'POSTGRES_DB')
        missing = [name for name in required if not os.getenv(name)]
        if missing:
            raise RuntimeError('PostgreSQL connection is not configured. Missing: ' + ', '.join(missing))
        url = URL.create(
            'postgresql+psycopg',
            username=os.environ['POSTGRES_USER'], password=os.environ['POSTGRES_PASSWORD'],
            host=os.environ['POSTGRES_HOST'], port=int(os.environ['POSTGRES_PORT']),
            database=os.environ['POSTGRES_DB'],
        )
    if url.get_backend_name() != 'postgresql' and not (
        url.get_backend_name() == 'sqlite' and (os.getenv('ALLOW_SQLITE_FOR_TESTS') == '1' or os.getenv('ALLOW_SQLITE_LOCAL') == '1')
    ):
        raise RuntimeError('Use PostgreSQL for deployment or explicitly enable SQLite for local development/tests.')
    return url

def initialize():
    url = database_url()
    engine = create_engine(
        url, pool_pre_ping=True, pool_recycle=1800,
        connect_args={'check_same_thread': False} if url.get_backend_name() == 'sqlite' else {},
    )
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)
