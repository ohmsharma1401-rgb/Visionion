"""Start the local API with a persistent JWT secret kept in ignored data/."""
import os
from pathlib import Path
import secrets
import sys
import uvicorn
from migrate_sqlite_to_postgres import migrate

root=Path(__file__).resolve().parents[1]
os.chdir(root)
sys.path.insert(0,str(root))
Path('data').mkdir(exist_ok=True)
for variable,filename in [('JWT_SECRET','local-jwt-secret.txt')]:
    path=Path('data',filename)
    if not path.exists(): path.write_text(secrets.token_urlsafe(32))
    os.environ.setdefault(variable,path.read_text().strip())
if not os.getenv('DATABASE_URL') and not os.getenv('POSTGRES_HOST'):
    os.environ['DATABASE_URL'] = 'sqlite:///' + str((root/'data/oniongrade.db').resolve()).replace('\\','/')
    os.environ['ALLOW_SQLITE_LOCAL'] = '1'
    print('Local development database: SQLite in data/oniongrade.db')
else:
    print('PostgreSQL:', migrate())
host = os.getenv('HOST', '0.0.0.0')
port = int(os.getenv('PORT', '8000'))
print(f'Starting OnionGrade AI on http://{host}:{port}')
uvicorn.run('backend.main:app', host=host, port=port)
