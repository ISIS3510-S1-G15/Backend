import sqlalchemy as sa
from alembic import op

revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not sa.inspect(op.get_bind()).has_table('place_selection_events'):
        op.create_table(
            'place_selection_events',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('restaurant_id', sa.String(), nullable=False),
            sa.Column('ms_since_app_open', sa.Integer(), nullable=False),
            sa.Column('meal_slot', sa.String(length=32), nullable=True),
            sa.Column('received_at', sa.DateTime(), server_default=sa.text("timezone('utc', now())"), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        for column in ('id', 'user_id', 'restaurant_id', 'meal_slot'):
            op.create_index(f'ix_place_selection_events_{column}', 'place_selection_events', [column])
    op.execute('ALTER TABLE "place_selection_events" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    op.drop_table('place_selection_events')
