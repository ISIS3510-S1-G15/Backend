import sqlalchemy as sa
from alembic import op

revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No server default and no backfill: NULL means a pre-Sprint 4 selection and is read as 'detail'.
    columns = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('place_selection_events')}
    if 'source' not in columns:
        op.add_column('place_selection_events', sa.Column('source', sa.String(length=16), nullable=True))
        op.create_index('ix_place_selection_events_source', 'place_selection_events', ['source'])


def downgrade() -> None:
    op.drop_index('ix_place_selection_events_source', table_name='place_selection_events')
    op.drop_column('place_selection_events', 'source')
