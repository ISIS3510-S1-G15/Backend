"""initial schema

Revision ID: 0001
Revises: 
Create Date: 2026-10-27 19:48:43.448961
"""
from alembic import op
import sqlalchemy as sa


revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('filter_usages',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('filter', sa.String(), nullable=True),
    sa.Column('screen', sa.String(), nullable=True),
    sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_filter_usages_filter'), 'filter_usages', ['filter'], unique=False)
    op.create_index(op.f('ix_filter_usages_id'), 'filter_usages', ['id'], unique=False)
    op.create_index(op.f('ix_filter_usages_screen'), 'filter_usages', ['screen'], unique=False)
    op.create_table('occupancy_checks',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('restaurant_id', sa.String(), nullable=True),
    sa.Column('screen', sa.String(), nullable=True),
    sa.Column('action', sa.String(), nullable=True),
    sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_occupancy_checks_action'), 'occupancy_checks', ['action'], unique=False)
    op.create_index(op.f('ix_occupancy_checks_id'), 'occupancy_checks', ['id'], unique=False)
    op.create_index(op.f('ix_occupancy_checks_restaurant_id'), 'occupancy_checks', ['restaurant_id'], unique=False)
    op.create_index(op.f('ix_occupancy_checks_screen'), 'occupancy_checks', ['screen'], unique=False)
    op.create_table('onboarding_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('session_id', sa.String(), nullable=True),
    sa.Column('event', sa.String(), nullable=True),
    sa.Column('step', sa.Integer(), nullable=True),
    sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_onboarding_events_event'), 'onboarding_events', ['event'], unique=False)
    op.create_index(op.f('ix_onboarding_events_id'), 'onboarding_events', ['id'], unique=False)
    op.create_index(op.f('ix_onboarding_events_session_id'), 'onboarding_events', ['session_id'], unique=False)
    op.create_table('profile_edits',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('install_id', sa.String(), nullable=True),
    sa.Column('field', sa.String(), nullable=True),
    sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_profile_edits_field'), 'profile_edits', ['field'], unique=False)
    op.create_index(op.f('ix_profile_edits_id'), 'profile_edits', ['id'], unique=False)
    op.create_index(op.f('ix_profile_edits_install_id'), 'profile_edits', ['install_id'], unique=False)
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('password_hash', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_table('zero_result_searches',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('query', sa.String(), nullable=True),
    sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_zero_result_searches_id'), 'zero_result_searches', ['id'], unique=False)
    op.create_index(op.f('ix_zero_result_searches_query'), 'zero_result_searches', ['query'], unique=False)
    op.create_table('app_opens',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('meal_slot', sa.String(), nullable=True),
    sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_app_opens_id'), 'app_opens', ['id'], unique=False)
    op.create_index(op.f('ix_app_opens_user_id'), 'app_opens', ['user_id'], unique=False)
    op.create_table('occupancy_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('restaurant_id', sa.String(), nullable=False),
    sa.Column('event', sa.String(), nullable=False),
    sa.Column('has_data', sa.Boolean(), nullable=True),
    sa.Column('timestamp', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_occupancy_events_event'), 'occupancy_events', ['event'], unique=False)
    op.create_index(op.f('ix_occupancy_events_id'), 'occupancy_events', ['id'], unique=False)
    op.create_index(op.f('ix_occupancy_events_restaurant_id'), 'occupancy_events', ['restaurant_id'], unique=False)
    op.create_index(op.f('ix_occupancy_events_timestamp'), 'occupancy_events', ['timestamp'], unique=False)
    op.create_index(op.f('ix_occupancy_events_user_id'), 'occupancy_events', ['user_id'], unique=False)
    op.create_table('occupancy_reports',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('restaurant_id', sa.String(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('level', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_occupancy_reports_created_at'), 'occupancy_reports', ['created_at'], unique=False)
    op.create_index(op.f('ix_occupancy_reports_id'), 'occupancy_reports', ['id'], unique=False)
    op.create_index(op.f('ix_occupancy_reports_restaurant_id'), 'occupancy_reports', ['restaurant_id'], unique=False)
    op.create_index(op.f('ix_occupancy_reports_user_id'), 'occupancy_reports', ['user_id'], unique=False)
    op.create_table('restaurant_views',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('restaurant_id', sa.String(), nullable=False),
    sa.Column('viewed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_restaurant_views_id'), 'restaurant_views', ['id'], unique=False)
    op.create_index(op.f('ix_restaurant_views_restaurant_id'), 'restaurant_views', ['restaurant_id'], unique=False)
    op.create_index(op.f('ix_restaurant_views_user_id'), 'restaurant_views', ['user_id'], unique=False)
    op.create_index(op.f('ix_restaurant_views_viewed_at'), 'restaurant_views', ['viewed_at'], unique=False)
    op.create_table('reviews',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('restaurant_id', sa.String(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('taste', sa.Integer(), nullable=False),
    sa.Column('attention', sa.Integer(), nullable=False),
    sa.Column('price', sa.Integer(), nullable=False),
    sa.Column('options', sa.Integer(), nullable=False),
    sa.Column('dietary_options', sa.JSON(), nullable=True),
    sa.Column('comment', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'restaurant_id', name='uq_review_user_restaurant')
    )
    op.create_index(op.f('ix_reviews_created_at'), 'reviews', ['created_at'], unique=False)
    op.create_index(op.f('ix_reviews_id'), 'reviews', ['id'], unique=False)
    op.create_index(op.f('ix_reviews_restaurant_id'), 'reviews', ['restaurant_id'], unique=False)
    op.create_index(op.f('ix_reviews_user_id'), 'reviews', ['user_id'], unique=False)
    op.create_table('saved_restaurants',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('restaurant_id', sa.String(), nullable=False),
    sa.Column('saved_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('user_id', 'restaurant_id')
    )
    op.create_table('user_profiles',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=True),
    sa.Column('cuisines', sa.JSON(), nullable=True),
    sa.Column('dietary_restrictions', sa.JSON(), nullable=True),
    sa.Column('meal_frequency', sa.String(), nullable=True),
    sa.Column('meal_times', sa.JSON(), nullable=True),
    sa.Column('budget', sa.String(), nullable=True),
    sa.Column('priorities', sa.JSON(), nullable=True),
    sa.Column('disliked_foods', sa.String(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('user_id')
    )


def downgrade() -> None:
    op.drop_table('user_profiles')
    op.drop_table('saved_restaurants')
    op.drop_index(op.f('ix_reviews_user_id'), table_name='reviews')
    op.drop_index(op.f('ix_reviews_restaurant_id'), table_name='reviews')
    op.drop_index(op.f('ix_reviews_id'), table_name='reviews')
    op.drop_index(op.f('ix_reviews_created_at'), table_name='reviews')
    op.drop_table('reviews')
    op.drop_index(op.f('ix_restaurant_views_viewed_at'), table_name='restaurant_views')
    op.drop_index(op.f('ix_restaurant_views_user_id'), table_name='restaurant_views')
    op.drop_index(op.f('ix_restaurant_views_restaurant_id'), table_name='restaurant_views')
    op.drop_index(op.f('ix_restaurant_views_id'), table_name='restaurant_views')
    op.drop_table('restaurant_views')
    op.drop_index(op.f('ix_occupancy_reports_user_id'), table_name='occupancy_reports')
    op.drop_index(op.f('ix_occupancy_reports_restaurant_id'), table_name='occupancy_reports')
    op.drop_index(op.f('ix_occupancy_reports_id'), table_name='occupancy_reports')
    op.drop_index(op.f('ix_occupancy_reports_created_at'), table_name='occupancy_reports')
    op.drop_table('occupancy_reports')
    op.drop_index(op.f('ix_occupancy_events_user_id'), table_name='occupancy_events')
    op.drop_index(op.f('ix_occupancy_events_timestamp'), table_name='occupancy_events')
    op.drop_index(op.f('ix_occupancy_events_restaurant_id'), table_name='occupancy_events')
    op.drop_index(op.f('ix_occupancy_events_id'), table_name='occupancy_events')
    op.drop_index(op.f('ix_occupancy_events_event'), table_name='occupancy_events')
    op.drop_table('occupancy_events')
    op.drop_index(op.f('ix_app_opens_user_id'), table_name='app_opens')
    op.drop_index(op.f('ix_app_opens_id'), table_name='app_opens')
    op.drop_table('app_opens')
    op.drop_index(op.f('ix_zero_result_searches_query'), table_name='zero_result_searches')
    op.drop_index(op.f('ix_zero_result_searches_id'), table_name='zero_result_searches')
    op.drop_table('zero_result_searches')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
    op.drop_index(op.f('ix_profile_edits_install_id'), table_name='profile_edits')
    op.drop_index(op.f('ix_profile_edits_id'), table_name='profile_edits')
    op.drop_index(op.f('ix_profile_edits_field'), table_name='profile_edits')
    op.drop_table('profile_edits')
    op.drop_index(op.f('ix_onboarding_events_session_id'), table_name='onboarding_events')
    op.drop_index(op.f('ix_onboarding_events_id'), table_name='onboarding_events')
    op.drop_index(op.f('ix_onboarding_events_event'), table_name='onboarding_events')
    op.drop_table('onboarding_events')
    op.drop_index(op.f('ix_occupancy_checks_screen'), table_name='occupancy_checks')
    op.drop_index(op.f('ix_occupancy_checks_restaurant_id'), table_name='occupancy_checks')
    op.drop_index(op.f('ix_occupancy_checks_id'), table_name='occupancy_checks')
    op.drop_index(op.f('ix_occupancy_checks_action'), table_name='occupancy_checks')
    op.drop_table('occupancy_checks')
    op.drop_index(op.f('ix_filter_usages_screen'), table_name='filter_usages')
    op.drop_index(op.f('ix_filter_usages_id'), table_name='filter_usages')
    op.drop_index(op.f('ix_filter_usages_filter'), table_name='filter_usages')
    op.drop_table('filter_usages')
