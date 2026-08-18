# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests import HttpCase, tagged


def _hoot_error_checker(message):
    return "[HOOT]" not in message


@tagged("post_install", "-at_install")
class TestCustomizationHoot(HttpCase):
    def test_hoot_owl_patches(self):
        """Run HOOT coverage of the OWL patches (form, list, search, kanban)."""
        self.browser_js(
            "/web/tests?headless&loglevel=2&preset=desktop&timeout=15000"
            "&filter=@web_customizer",
            "",
            "",
            login="admin",
            timeout=300,
            success_signal="[HOOT] Test suite succeeded",
            error_checker=_hoot_error_checker,
        )
