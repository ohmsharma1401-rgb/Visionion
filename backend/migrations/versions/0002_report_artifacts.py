"""Persist PDF byte hashes separately from analysis hashes."""
from alembic import op
import sqlalchemy as sa
revision='0002'
down_revision='0001'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('report_artifacts',sa.Column('inspection_id',sa.String(36),primary_key=True),sa.Column('pdf_sha256',sa.String(64),nullable=False))

def downgrade(): op.drop_table('report_artifacts')
