from . import models
from .models.md_view import VIEW_SPECS, refresh_md_view

import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Create the public mirror views (md.entity, md.entity_column,
    gnr.module). Re-runs on every upgrade via each model's init(); a missing
    DW schema yields empty views instead of a broken model."""
    for view, schema, table, _columns in VIEW_SPECS:
        src = refresh_md_view(env, view, schema, table, _columns)
        if not src:
            _logger.warning(
                "DW source %s.%s not found - %s will return no rows.",
                schema, table, view)


def uninstall_hook(env):
    cr = env.cr
    for view, _schema, _table, _columns in VIEW_SPECS:
        cr.execute(f'DROP VIEW IF EXISTS public."{view}" CASCADE')
