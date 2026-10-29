import sqlalchemy as sa
from alembic import op

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not sa.inspect(op.get_bind()).has_table('recommendation_events'):
        op.create_table(
            'recommendation_events',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('recommended_id', sa.String(), nullable=False),
            sa.Column('recommended_level', sa.Float(), nullable=True),
            sa.Column('occupancy_level', sa.String(), nullable=False),
            sa.Column('alternative_id', sa.String(), nullable=True),
            sa.Column('timestamp', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        for column in ('id', 'user_id', 'recommended_id', 'occupancy_level', 'timestamp'):
            op.create_index(f'ix_recommendation_events_{column}', 'recommendation_events', [column])
    op.execute('ALTER TABLE "recommendation_events" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    op.drop_table('recommendation_events')
