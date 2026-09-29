"""Add verified email accounts and single-use signup codes."""
from alembic import op
import sqlalchemy as sa

revision='0003'
down_revision='0002'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('users',sa.Column('id',sa.String(36),primary_key=True),sa.Column('email',sa.String(254),nullable=False),sa.Column('name',sa.String(120),nullable=False),sa.Column('password_hash',sa.String(255),nullable=False),sa.Column('verified_at',sa.DateTime(),nullable=True),sa.Column('created_at',sa.DateTime(),nullable=False))
    op.create_index('ix_users_email','users',['email'],unique=True)
    op.create_table('email_otps',sa.Column('user_id',sa.String(36),primary_key=True),sa.Column('code_hash',sa.String(64),nullable=False),sa.Column('expires_at',sa.DateTime(),nullable=False),sa.Column('sent_at',sa.DateTime(),nullable=False),sa.Column('attempts',sa.Integer(),nullable=False))

def downgrade():
    op.drop_table('email_otps')
    op.drop_index('ix_users_email',table_name='users')
    op.drop_table('users')
