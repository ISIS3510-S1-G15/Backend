import sqlalchemy as sa
from alembic import op

from app.restaurant_seed import RESTAURANT_SEED

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    table = op.create_table(
        'restaurants',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('location', sa.String(), nullable=False),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('image_key', sa.String(), nullable=True),
        sa.Column('image_url', sa.String(), nullable=True),
        sa.Column('rating', sa.Float(), nullable=False),
        sa.Column('review_count', sa.Integer(), nullable=False),
        sa.Column('price', sa.String(), nullable=False),
        sa.Column('wait_time', sa.String(), nullable=False),
        sa.Column('tags', sa.JSON(), nullable=False),
        sa.Column('hours', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('map_x', sa.Float(), nullable=False),
        sa.Column('map_y', sa.Float(), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('menu', sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.execute('ALTER TABLE "restaurants" ENABLE ROW LEVEL SECURITY')
    op.bulk_insert(table, RESTAURANT_SEED)


def downgrade() -> None:
    op.drop_table('restaurants')
