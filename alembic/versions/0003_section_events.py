import sqlalchemy as sa
from alembic import op

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'section_events',
        sa.Column('event_id', sa.Uuid(), nullable=False),
        sa.Column('event_type', sa.String(length=32), nullable=False),
        sa.Column('section', sa.String(length=32), nullable=False),
        sa.Column('action', sa.String(length=48), nullable=True),
        sa.Column('visit_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('client_timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('extra', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('event_id'),
    )
    op.create_index('ix_section_events_visit_id', 'section_events', ['visit_id'])
    op.create_index('ix_section_events_user_id', 'section_events', ['user_id'])
    op.create_index(
        'ix_section_events_section_type_time',
        'section_events',
        ['section', 'event_type', 'client_timestamp'],
    )
    op.execute('ALTER TABLE "section_events" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    op.drop_table('section_events')
