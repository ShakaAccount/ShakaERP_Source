"""Writable public mirror views for md.category / md.category_member."""
from odoo.addons.entity.models.md_view import refresh_writable_view

_CATEGORY_COLUMNS = {
    'id': 'bigint',
    'code': 'varchar',
    'title': 'varchar',
    'english_title': 'varchar',
    'parent_id': 'bigint',
    'root_id': 'bigint',
    'reserved_attibute1': 'varchar',
    'reserved_attibute2': 'varchar',
    'reserved_attibute3': 'varchar',
    'creator_user_id': 'integer',
    'creation_date': 'timestamp',
    'editor_user_id': 'integer',
    'modification_date': 'timestamp',
    'company_id': 'integer',
    'entity_id': 'integer',
    'is_node_only': 'boolean',
    'is_user_defined': 'boolean',
}

_CATEGORY_MEMBER_COLUMNS = {
    'id': 'bigint',
    'category_id': 'bigint',
    'member_id': 'bigint',
    'creator_user_id': 'integer',
    'creation_date': 'timestamp',
    'editor_user_id': 'integer',
    'modification_date': 'timestamp',
    'entity_id': 'integer',
}

CATEGORY_VIEW = ('raes_md_category', 'md', 'category', _CATEGORY_COLUMNS)
CATEGORY_MEMBER_VIEW = ('raes_md_category_member', 'md', 'category_member',
                        _CATEGORY_MEMBER_COLUMNS)