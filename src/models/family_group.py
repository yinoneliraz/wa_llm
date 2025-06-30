# Extension to the Group model for family functionality
# This file extends the existing group model without modifying it directly

from sqlmodel import Field
from .group import BaseGroup as OriginalBaseGroup


class FamilyBaseGroup(OriginalBaseGroup):
    """Extended BaseGroup with family functionality flag"""
    family_group: bool = Field(default=False, description="Enable family bot features for this group")


# For backwards compatibility, we can use this approach:
# In a real migration, you would add this column to the existing group table:
# ALTER TABLE group ADD COLUMN family_group BOOLEAN DEFAULT FALSE;

# Usage instructions:
# 1. Add family_group column to your group table via migration
# 2. Update existing groups to set family_group=True for your family group
# 3. The family handler will only process messages from groups where family_group=True