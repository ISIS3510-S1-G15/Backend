import sqlalchemy as sa
from alembic import op

revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not sa.inspect(op.get_bind()).has_table('occupancy_propagation_events'):
        op.create_table(
            'occupancy_propagation_events',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('report_id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('source', sa.String(length=16), nullable=False),
            sa.Column('ms_since_previous_refresh', sa.Integer(), nullable=True),
            sa.Column('seen_at', sa.DateTime(), server_default=sa.text("timezone('utc', now())"), nullable=False),
            sa.ForeignKeyConstraint(['report_id'], ['occupancy_reports.id']),
            sa.ForeignKeyConstraint(['user_id'], ['users.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id', 'report_id', name='uq_propagation_user_report'),
        )
        for column in ('id', 'report_id', 'user_id', 'source'):
            op.create_index(f'ix_occupancy_propagation_events_{column}', 'occupancy_propagation_events', [column])
    op.execute('ALTER TABLE "occupancy_propagation_events" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    op.drop_table('occupancy_propagation_events')
