"""enable row level security

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-27 20:30:00
"""
from alembic import op

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None

TABLES = [
    'app_opens',
    'filter_usages',
    'occupancy_checks',
    'occupancy_events',
    'occupancy_reports',
    'onboarding_events',
    'profile_edits',
    'restaurant_views',
    'reviews',
    'saved_restaurants',
    'user_profiles',
    'users',
    'zero_result_searches',
]


def upgrade() -> None:
    for table in TABLES:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    for table in TABLES:
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
