import sqlalchemy as sa
from alembic import op

from app.catalog_seed import CATALOG_SEED

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    table = op.create_table(
        'catalog_options',
        sa.Column('group_key', sa.String(length=48), nullable=False),
        sa.Column('value', sa.String(length=64), nullable=False),
        sa.Column('label', sa.String(), nullable=False),
        sa.Column('detail', sa.String(), nullable=True),
        sa.Column('emoji', sa.String(length=16), nullable=True),
        sa.Column('extra', sa.JSON(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('group_key', 'value'),
    )
    op.execute('ALTER TABLE "catalog_options" ENABLE ROW LEVEL SECURITY')
    op.bulk_insert(table, CATALOG_SEED)


def downgrade() -> None:
    op.drop_table('catalog_options')
