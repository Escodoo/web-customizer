# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class CustomizationCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env["ir.model"]._get("res.partner")
        cls.form_view = cls.env["ir.ui.view"].create(
            {
                "name": "customization.tester.partner.form",
                "model": "res.partner",
                "type": "form",
                "arch": """
                    <form>
                        <sheet>
                            <group>
                                <field name="name"/>
                                <field name="email"/>
                                <field name="phone"/>
                            </group>
                        </sheet>
                    </form>
                """,
            }
        )
        cls.list_view = cls.env["ir.ui.view"].create(
            {
                "name": "customization.tester.partner.list",
                "model": "res.partner",
                "type": "list",
                "arch": """
                    <list>
                        <field name="name"/>
                        <field name="email"/>
                    </list>
                """,
            }
        )
        cls.search_view = cls.env["ir.ui.view"].create(
            {
                "name": "customization.tester.partner.search",
                "model": "res.partner",
                "type": "search",
                "arch": """
                    <search>
                        <field name="name"/>
                        <field name="email"/>
                    </search>
                """,
            }
        )

    def _create_bundle(self, code="client_test", operations=None):
        vals = {
            "name": "Test bundle",
            "code": code,
        }
        if operations:
            vals["operation_ids"] = operations
        return self.env["customization.bundle"].create(vals)
