"""mark is_invalidated column as added

Revision ID: b2c3d4e5f6g7
Revises: bd404fed3872
Create Date: 2026-01-07 18:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6g7'
down_revision: Union[str, Sequence[str], None] = 'bd404fed3872'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # is_invalidated 字段已通过其他方式添加到数据库中，此迁移仅用于标记版本
    pass


def downgrade() -> None:
    """Downgrade schema."""
    # 由于字段已存在且正在使用，不执行删除操作
    pass
