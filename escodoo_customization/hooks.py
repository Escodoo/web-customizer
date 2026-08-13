# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

_logger = logging.getLogger(__name__)


def uninstall_hook(env):
    """Remove compiler-generated fields and views that live only in the database."""
    operations = env["customization.operation"].sudo().search([])
    views = operations.mapped("generated_view_id").exists()
    fields = operations.mapped("generated_field_id").exists()
    if views:
        _logger.info(
            "Uninstalling escodoo_customization: removing %s generated views",
            len(views),
        )
        views.unlink()
    if fields:
        _logger.info(
            "Uninstalling escodoo_customization: removing %s generated fields",
            len(fields),
        )
        fields.unlink()
