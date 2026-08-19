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
        cls.kanban_view = cls.env["ir.ui.view"].create(
            {
                "name": "customization.tester.partner.kanban",
                "model": "res.partner",
                "type": "kanban",
                "arch": """
                    <kanban>
                        <templates>
                            <t t-name="card">
                                <field name="name"/>
                                <field name="email"/>
                                <button
                                    name="toggle_active"
                                    type="object"
                                    string="Archive"
                                />
                                <button type="edit" string="Edit"/>
                            </t>
                        </templates>
                    </kanban>
                """,
            }
        )
        cls.board_kanban_view = cls.env["ir.ui.view"].create(
            {
                "name": "customization.tester.partner.kanban.board",
                "model": "res.partner",
                "type": "kanban",
                "arch": """
                    <kanban default_group_by="company_type">
                        <header>
                            <button
                                name="toggle_active"
                                type="object"
                                string="Archive"
                                display="always"
                            />
                        </header>
                        <progressbar
                            field="company_type"
                            colors='{"person": "success", "company": "warning"}'
                        />
                        <templates>
                            <t t-name="card">
                                <field name="name"/>
                            </t>
                        </templates>
                    </kanban>
                """,
            }
        )
        cls.pivot_view = cls.env["ir.ui.view"].create(
            {
                "name": "customization.tester.partner.pivot",
                "model": "res.partner",
                "type": "pivot",
                "arch": """
                    <pivot>
                        <field name="company_type" type="row"/>
                        <field name="color" type="measure"/>
                    </pivot>
                """,
            }
        )
        cls.graph_view = cls.env["ir.ui.view"].create(
            {
                "name": "customization.tester.partner.graph",
                "model": "res.partner",
                "type": "graph",
                "arch": """
                    <graph>
                        <field name="company_type"/>
                        <field name="color" type="measure"/>
                    </graph>
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

    def _form_with_page(self):
        return self.env["ir.ui.view"].create(
            {
                "name": "customization.tester.partner.notebook",
                "model": "res.partner",
                "type": "form",
                "arch": """
                    <form>
                        <header>
                            <button
                                name="toggle_active"
                                type="object"
                                string="Archive"
                            />
                        </header>
                        <sheet>
                            <group>
                                <field name="name"/>
                                <field name="email"/>
                            </group>
                            <notebook>
                                <page name="extra_info" string="Extra">
                                    <field name="phone"/>
                                </page>
                            </notebook>
                        </sheet>
                    </form>
                """,
            }
        )

    def _form_with_unnamed_page(self):
        return self.env["ir.ui.view"].create(
            {
                "name": "customization.tester.partner.unnamed.page",
                "model": "res.partner",
                "type": "form",
                "arch": """
                    <form>
                        <sheet>
                            <group>
                                <field name="name"/>
                                <field name="email"/>
                            </group>
                            <notebook>
                                <page string="Field Service">
                                    <field name="phone"/>
                                </page>
                            </notebook>
                        </sheet>
                    </form>
                """,
            }
        )

    def _form_with_subview(self):
        """Form whose x2many carries a written list, plus a name it shares."""
        return self.env["ir.ui.view"].create(
            {
                "name": "customization.tester.partner.subview",
                "model": "res.partner",
                "type": "form",
                "arch": """
                    <form>
                        <sheet>
                            <group>
                                <field name="name"/>
                                <field name="company_id"/>
                            </group>
                            <field name="bank_ids">
                                <list>
                                    <field name="acc_number"/>
                                    <field name="company_id"/>
                                </list>
                            </field>
                        </sheet>
                    </form>
                """,
            }
        )

    def _form_with_kanban_subview(self):
        """Form whose x2many writes a kanban instead of a list."""
        return self.env["ir.ui.view"].create(
            {
                "name": "customization.tester.partner.subview.kanban",
                "model": "res.partner",
                "type": "form",
                "arch": """
                    <form>
                        <sheet>
                            <field name="bank_ids">
                                <kanban>
                                    <templates>
                                        <t t-name="card">
                                            <field name="acc_number"/>
                                        </t>
                                    </templates>
                                </kanban>
                            </field>
                        </sheet>
                    </form>
                """,
            }
        )

    def _form_with_referenced_subview(self):
        """Form whose x2many borrows its list from a res.partner.bank view."""
        return self.env["ir.ui.view"].create(
            {
                "name": "customization.tester.partner.subview.ref",
                "model": "res.partner",
                "type": "form",
                "arch": """
                    <form>
                        <sheet>
                            <group>
                                <field name="name"/>
                            </group>
                            <field name="bank_ids"/>
                        </sheet>
                    </form>
                """,
            }
        )

    def _form_with_group(self):
        return self.env["ir.ui.view"].create(
            {
                "name": "customization.tester.partner.group",
                "model": "res.partner",
                "type": "form",
                "arch": """
                    <form>
                        <sheet>
                            <group name="site_block" string="Site">
                                <field name="phone"/>
                            </group>
                            <group string="Notes">
                                <field name="email"/>
                            </group>
                        </sheet>
                    </form>
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
