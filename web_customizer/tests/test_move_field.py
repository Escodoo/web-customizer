# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from lxml import etree

from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import CustomizationCase


@tagged("post_install", "-at_install")
class TestCustomizationMoveField(CustomizationCase):
    """A move relocates the node the view already declares.

    ``position="move"`` keeps the original element, so the field arrives with
    the attributes the base view gave it and goes back where it was once the
    operation is dropped.
    """

    def _move(
        self,
        view,
        field_name,
        anchor,
        anchor_kind="field",
        position="after",
        view_type="form",
    ):
        return Command.create(
            {
                "type": "move_field",
                "model_id": self.partner_model.id,
                "view_id": view.id,
                "view_type": view_type,
                "anchor_kind": anchor_kind,
                "anchor_name": anchor,
                "position": position,
                "payload": {"field_name": field_name},
            }
        )

    def _tree(self, view):
        return etree.fromstring(view.get_combined_arch())

    def _field_order(self, view, xpath="//group"):
        parent = self._tree(view).xpath(xpath)[0]
        return [node.get("name") for node in parent.xpath("./field")]

    def test_move_a_field_after_another_one(self):
        bundle = self._create_bundle(
            code="client_move_after",
            operations=[self._move(self.form_view, "phone", "name")],
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        self.assertEqual(self._field_order(self.form_view), ["name", "phone", "email"])

    def test_move_a_field_into_a_page(self):
        view = self._form_with_page()
        bundle = self._create_bundle(
            code="client_move_page",
            operations=[
                self._move(
                    view,
                    "email",
                    "extra_info",
                    anchor_kind="page",
                    position="inside",
                )
            ],
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        tree = self._tree(view)
        # The node moved instead of being copied, so the group lost it.
        self.assertEqual(len(tree.xpath("//field[@name='email']")), 1)
        self.assertTrue(tree.xpath("//page[@name='extra_info']/field[@name='email']"))
        self.assertEqual(self._field_order(view), ["name"])

    def test_move_keeps_the_attributes_of_the_original_node(self):
        view = self.env["ir.ui.view"].create(
            {
                "name": "customization.tester.partner.decorated",
                "model": "res.partner",
                "type": "form",
                "arch": """
                    <form>
                        <sheet>
                            <group>
                                <field name="name"/>
                                <field name="email" widget="email"
                                       string="Contact mail"/>
                            </group>
                        </sheet>
                    </form>
                """,
            }
        )
        bundle = self._create_bundle(
            code="client_move_attrs",
            operations=[
                self._move(view, "email", "name", position="before"),
            ],
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        node = self._tree(view).xpath("//field[@name='email']")[0]
        self.assertEqual(node.get("widget"), "email")
        self.assertEqual(node.get("string"), "Contact mail")
        self.assertEqual(self._field_order(view), ["email", "name"])

    def test_dropping_the_operation_restores_the_original_position(self):
        bundle = self._create_bundle(
            code="client_move_restore",
            operations=[self._move(self.form_view, "phone", "name")],
        )
        bundle.action_apply()
        self.assertEqual(self._field_order(self.form_view), ["name", "phone", "email"])
        bundle.operation_ids.unlink()
        self.form_view.invalidate_recordset()
        self.assertEqual(self._field_order(self.form_view), ["name", "email", "phone"])

    def test_move_of_a_field_outside_the_view_is_broken(self):
        bundle = self._create_bundle(
            code="client_move_missing",
            operations=[self._move(self.form_view, "mobile", "name")],
        )
        bundle.action_apply()
        operation = bundle.operation_ids
        self.assertEqual(operation.state, "broken")
        self.assertIn("cannot be moved", operation.broken_reason)

    def test_move_of_an_ambiguous_field_is_broken(self):
        view = self.env["ir.ui.view"].create(
            {
                "name": "customization.tester.partner.twice",
                "model": "res.partner",
                "type": "form",
                "arch": """
                    <form>
                        <sheet>
                            <group>
                                <field name="name"/>
                                <field name="email"/>
                            </group>
                            <group invisible="1">
                                <field name="email"/>
                            </group>
                        </sheet>
                    </form>
                """,
            }
        )
        bundle = self._create_bundle(
            code="client_move_ambiguous",
            operations=[self._move(view, "email", "name")],
        )
        bundle.action_apply()
        operation = bundle.operation_ids
        self.assertEqual(operation.state, "broken")
        self.assertIn("ambiguous", operation.broken_reason)

    def test_move_next_to_itself_is_broken(self):
        bundle = self._create_bundle(
            code="client_move_self",
            operations=[self._move(self.form_view, "email", "email")],
        )
        bundle.action_apply()
        operation = bundle.operation_ids
        self.assertEqual(operation.state, "broken")
        self.assertIn("itself", operation.broken_reason)

    def test_move_cannot_replace_the_anchor(self):
        bundle = self._create_bundle(
            code="client_move_replace",
            operations=[
                self._move(self.form_view, "phone", "name", position="replace")
            ],
        )
        bundle.action_apply()
        operation = bundle.operation_ids
        self.assertEqual(operation.state, "broken")
        self.assertIn("replace", operation.broken_reason)

    def test_a_moved_field_cannot_also_be_placed(self):
        first = self._create_bundle(
            code="client_move_owner",
            operations=[self._move(self.form_view, "phone", "name")],
        )
        first.action_apply()
        with self.assertRaises(ValidationError) as error:
            self._create_bundle(
                code="client_move_rival",
                operations=[
                    Command.create(
                        {
                            "type": "place_field",
                            "model_id": self.partner_model.id,
                            "view_id": self.form_view.id,
                            "view_type": "form",
                            "anchor_kind": "field",
                            "anchor_name": "email",
                            "position": "after",
                            "payload": {"field_name": "phone"},
                        }
                    )
                ],
            )
        self.assertIn("client_move_owner", str(error.exception))

    def test_move_a_pivot_measure(self):
        bundle = self._create_bundle(
            code="client_move_measure",
            operations=[
                self._move(
                    self.pivot_view,
                    "color",
                    "company_type",
                    position="before",
                    view_type="pivot",
                )
            ],
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        nodes = self._tree(self.pivot_view).xpath("//field")
        self.assertEqual(
            [node.get("name") for node in nodes], ["color", "company_type"]
        )
        # The role travels with the node, so it never has to be restated.
        self.assertEqual(nodes[0].get("type"), "measure")

    def test_move_from_the_ui_creates_the_operation(self):
        view = self._form_with_page()
        bundle = self._create_bundle(code="client_move_ui")
        self.env["customization.bundle"].create_from_ui(
            {
                "bundle_id": bundle.id,
                "action": "move_after",
                "model": "res.partner",
                "view_id": view.id,
                "view_type": "form",
                "anchor_name": "extra_info",
                "anchor_kind": "page",
                "payload": {"field_name": "email"},
                "apply": True,
            }
        )
        operation = bundle.operation_ids
        self.assertEqual(operation.type, "move_field")
        self.assertEqual(operation.state, "applied")
        self.assertTrue(
            self._tree(view).xpath("//page[@name='extra_info']/field[@name='email']")
        )

    def test_the_ui_refuses_to_move_a_field_onto_itself(self):
        bundle = self._create_bundle(code="client_move_ui_self")
        with self.assertRaises(UserError):
            self.env["customization.bundle"].create_from_ui(
                {
                    "bundle_id": bundle.id,
                    "action": "move_after",
                    "model": "res.partner",
                    "view_id": self.form_view.id,
                    "view_type": "form",
                    "anchor_name": "email",
                    "anchor_kind": "field",
                    "payload": {"field_name": "email"},
                    "apply": True,
                }
            )
