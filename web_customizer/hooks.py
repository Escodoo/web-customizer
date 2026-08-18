# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from .models.compiler import rebind_generated_xmlids

_logger = logging.getLogger(__name__)


def health_check_on_upgrade(env):
    """Re-resolve applied anchors after a module install or upgrade.

    ``post_init_hook`` only runs on first install. This is called from
    ``customization.bundle._register_hook`` when the registry loaded at
    least one updated module (``-u odoo``, ``-u sale``, …), so dead
    anchors surface without a consultant clicking Health Check.
    Restored anchors rewrite their inherit in the same pass.
    """
    bundles = env["customization.bundle"].sudo().search([])
    if not bundles:
        return
    _logger.info(
        "Health-checking %s customization bundle(s) after module update",
        len(bundles),
    )
    try:
        rebind_generated_xmlids(env)
        bundles._health_check()
    except Exception:
        _logger.exception("Customization health check after upgrade failed")


def uninstall_hook(env):
    """Leave compiled fields, views and menus in the database.

    Their XML IDs belong to the bundle code (the future exported addon),
    not to this ledger. Uninstalling the authoring tool must not wipe
    unexported customizations. Unlink a bundle or operation to undo.
    """
    rebind_generated_xmlids(env)
    _logger.info(
        "Uninstalling escodoo_customization: compiled customizations stay "
        "in the database (XML IDs belong to each bundle code)"
    )
