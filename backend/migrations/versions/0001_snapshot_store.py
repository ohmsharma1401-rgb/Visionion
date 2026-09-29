"""Initial prototype snapshot store."""
from alembic import op
import sqlalchemy as sa
revision='0001'
down_revision=None
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('inspections',sa.Column('id',sa.String(36),primary_key=True),sa.Column('owner',sa.String(100),nullable=False),sa.Column('payload',sa.Text(),nullable=False),sa.Column('report_hash',sa.String(64),nullable=False),sa.Column('created_at',sa.DateTime(),nullable=False))
    op.create_index('ix_inspections_owner','inspections',['owner'])
    op.create_table('audit_logs',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('payload',sa.Text(),nullable=False),sa.Column('prev_hash',sa.String(64),nullable=False),sa.Column('hash',sa.String(64),nullable=False))

def downgrade():
    op.drop_table('audit_logs')
    op.drop_index('ix_inspections_owner',table_name='inspections')
    op.drop_table('inspections')
