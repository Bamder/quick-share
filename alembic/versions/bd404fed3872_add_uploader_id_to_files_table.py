"""add uploader_id to files table

Revision ID: bd404fed3872
Revises: 2e628095c88f
Create Date: 2026-01-05 22:06:42.841592

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bd404fed3872'
down_revision: Union[str, Sequence[str], None] = '2e628095c88f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 添加 uploader_id 字段到 files 表
    op.add_column('files', 
        sa.Column('uploader_id', sa.Integer(), nullable=True, comment='分享者用户ID')
    )
    # 添加外键约束
    op.create_foreign_key(
        'fk_files_uploader_id',  # 约束名称
        'files',  # 表名
        'users',  # 引用表
        ['uploader_id'],  # 本地列
        ['id'],  # 引用列
        ondelete='SET NULL'  # 用户删除时设置为 NULL
    )


def downgrade() -> None:
    """Downgrade schema."""
    # 删除外键约束
    op.drop_constraint('fk_files_uploader_id', 'files', type_='foreignkey')
    # 删除 uploader_id 字段
    op.drop_column('files', 'uploader_id')
