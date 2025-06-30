"""Add family functionality

Revision ID: add_family_functionality
Revises: [your_previous_revision_id]
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'add_family_functionality'
down_revision: Union[str, None] = 'bbba88e22126'  # Replace with your actual previous revision
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add family functionality tables and columns"""
    
    # Add family_group column to existing group table
    op.add_column('group', sa.Column('family_group', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    
    # Create grocerylist table
    op.create_table('grocerylist',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('group_jid', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True, default='Shopping List'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['group_jid'], ['group.group_jid'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create groceryitem table
    op.create_table('groceryitem',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('list_id', sa.String(), nullable=False),
        sa.Column('item_name', sa.String(length=255), nullable=False),
        sa.Column('quantity', sa.String(length=50), nullable=True),
        sa.Column('added_by', sa.String(length=255), nullable=False),
        sa.Column('completed', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('completed_by', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['added_by'], ['sender.jid'], ),
        sa.ForeignKeyConstraint(['completed_by'], ['sender.jid'], ),
        sa.ForeignKeyConstraint(['list_id'], ['grocerylist.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create reminder table
    op.create_table('reminder',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('group_jid', sa.String(length=255), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=False),
        sa.Column('message', sa.String(length=1000), nullable=False),
        sa.Column('due_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('recurring_pattern', sa.String(length=50), nullable=True),
        sa.Column('recurring_interval', sa.Integer(), nullable=True),
        sa.Column('completed', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('sent', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['sender.jid'], ),
        sa.ForeignKeyConstraint(['group_jid'], ['group.group_jid'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create childscheduleentry table
    op.create_table('childscheduleentry',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('group_jid', sa.String(length=255), nullable=False),
        sa.Column('child_name', sa.String(length=100), nullable=False),
        sa.Column('activity_type', sa.String(length=50), nullable=False),
        sa.Column('notes', sa.String(length=500), nullable=True),
        sa.Column('recorded_by', sa.String(length=255), nullable=False),
        sa.Column('activity_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('duration_minutes', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['group_jid'], ['group.group_jid'], ),
        sa.ForeignKeyConstraint(['recorded_by'], ['sender.jid'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for better performance
    op.create_index('idx_grocery_list_group', 'grocerylist', ['group_jid'])
    op.create_index('idx_grocery_item_list', 'groceryitem', ['list_id'])
    op.create_index('idx_grocery_item_completed', 'groceryitem', ['completed'])
    
    op.create_index('idx_reminder_group', 'reminder', ['group_jid'])
    op.create_index('idx_reminder_due_time', 'reminder', ['due_time'])
    op.create_index('idx_reminder_completed', 'reminder', ['completed'])
    op.create_index('idx_reminder_sent', 'reminder', ['sent'])
    
    op.create_index('idx_schedule_group', 'childscheduleentry', ['group_jid'])
    op.create_index('idx_schedule_child', 'childscheduleentry', ['child_name'])
    op.create_index('idx_schedule_activity', 'childscheduleentry', ['activity_type'])
    op.create_index('idx_schedule_time', 'childscheduleentry', ['activity_time'])


def downgrade() -> None:
    """Remove family functionality tables and columns"""
    
    # Drop indexes first
    op.drop_index('idx_schedule_time', table_name='childscheduleentry')
    op.drop_index('idx_schedule_activity', table_name='childscheduleentry')
    op.drop_index('idx_schedule_child', table_name='childscheduleentry')
    op.drop_index('idx_schedule_group', table_name='childscheduleentry')
    
    op.drop_index('idx_reminder_sent', table_name='reminder')
    op.drop_index('idx_reminder_completed', table_name='reminder')
    op.drop_index('idx_reminder_due_time', table_name='reminder')
    op.drop_index('idx_reminder_group', table_name='reminder')
    
    op.drop_index('idx_grocery_item_completed', table_name='groceryitem')
    op.drop_index('idx_grocery_item_list', table_name='groceryitem')
    op.drop_index('idx_grocery_list_group', table_name='grocerylist')
    
    # Drop tables in reverse order (due to foreign key constraints)
    op.drop_table('childscheduleentry')
    op.drop_table('reminder')
    op.drop_table('groceryitem')
    op.drop_table('grocerylist')
    
    # Drop the added column
    op.drop_column('group', 'family_group')