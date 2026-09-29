"""Start a local-only demo with generated credentials kept in ignored data/."""
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
for variable,filename in [('DEMO_PASSWORD','local-demo-password.txt'),('JWT_SECRET','local-jwt-secret.txt')]:
    path=Path('data',filename)
    if not path.exists(): path.write_text(secrets.token_urlsafe(32))
    os.environ.setdefault(variable,path.read_text().strip())
if not os.getenv('DATABASE_URL') and not os.getenv('POSTGRES_HOST'):
    os.environ['DATABASE_URL'] = 'sqlite:///' + str((root/'data/oniongrade.db').resolve()).replace('\\','/')
    os.environ['ALLOW_SQLITE_LOCAL'] = '1'
    print('Local development database: SQLite in data/oniongrade.db')
else:
    print('PostgreSQL:', migrate())
print('Local demo: username inspector; password saved in data/local-demo-password.txt')
uvicorn.run('backend.main:app',host='127.0.0.1',port=8000)
