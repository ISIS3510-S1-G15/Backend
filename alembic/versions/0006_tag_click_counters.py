import sqlalchemy as sa
from alembic import op

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not sa.inspect(op.get_bind()).has_table('tag_click_counters'):
        op.create_table(
            'tag_click_counters',
            sa.Column('tag', sa.String(), nullable=False),
            sa.Column('count', sa.Integer(), nullable=False),
            sa.Column('last_updated', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
            sa.PrimaryKeyConstraint('tag'),
        )
        op.create_index('ix_tag_click_counters_tag', 'tag_click_counters', ['tag'])
    op.execute('ALTER TABLE "tag_click_counters" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    op.drop_table('tag_click_counters')
