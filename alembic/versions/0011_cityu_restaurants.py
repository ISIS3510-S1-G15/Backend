import sqlalchemy as sa
from alembic import op

from app.cityu_seed import CITYU_RESTAURANT_SEED

revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    table = sa.Table('restaurants', sa.MetaData(), autoload_with=bind)
    existing = {row[0] for row in bind.execute(sa.select(table.c.id))}
    rows = [row for row in CITYU_RESTAURANT_SEED if row['id'] not in existing]
    if rows:
        op.bulk_insert(table, rows)


def downgrade() -> None:
    ids = [row['id'] for row in CITYU_RESTAURANT_SEED]
    op.execute(sa.text('DELETE FROM restaurants WHERE id = ANY(:ids)').bindparams(ids=ids))
