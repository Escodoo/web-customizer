# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestCustomizationTour(HttpCase):
    def test_wand_opens_form_dialog(self):
        self.start_tour(
            "/odoo/res.partner/1",
            "web_customizer_wand_form",
            login="admin",
        )
