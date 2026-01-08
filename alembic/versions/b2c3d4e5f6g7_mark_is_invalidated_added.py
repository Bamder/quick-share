"""mark is_invalidated column as added

Revision ID: b2c3d4e5f6g7
Revises: bd404fed3872
Create Date: 2026-01-07 18:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6g7'
down_revision: Union[str, Sequence[str], None] = 'bd404fed3872'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 检查列是否已存在，如果不存在则添加
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns('files')]
    
    if 'is_invalidated' not in columns:
        # 添加 is_invalidated 字段到 files 表
        op.add_column('files', 
            sa.Column('is_invalidated', sa.Boolean(), nullable=True, server_default='0', comment='是否已被废弃')
        )
        print("[成功] 已添加 is_invalidated 列")
    else:
        print("[提示] is_invalidated 列已存在，跳过添加")


def downgrade() -> None:
    """Downgrade schema."""
    # 检查列是否存在，如果存在则删除
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns('files')]
    
    if 'is_invalidated' in columns:
        # 删除 is_invalidated 字段
        op.drop_column('files', 'is_invalidated')
        print("[成功] 已删除 is_invalidated 列")
    else:
        print("[提示] is_invalidated 列不存在，跳过删除")
