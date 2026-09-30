import pytest
from backend.database import database_url

@pytest.mark.parametrize('scheme', ['postgres','postgresql','postgresql+psycopg'])
def test_managed_postgres_uses_installed_driver(monkeypatch,scheme):
    monkeypatch.setenv('DATABASE_URL',f'{scheme}://user:password@example.invalid:6543/postgres?sslmode=require')
    url=database_url()
    assert url.drivername=='postgresql+psycopg'
    assert url.host=='example.invalid'
    assert url.port==6543
    assert url.query['sslmode']=='require'
