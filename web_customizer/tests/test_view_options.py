# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from lxml import etree

from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import CustomizationCase


@tagged("post_install", "-at_install")
class TestCustomizationViewOptions(CustomizationCase):
    """Options the arch parsers read off the view root itself."""

    def _set_options(self, view, view_type, attributes):
        return Command.create(
            {
                "type": "set_view_attribute",
                "model_id": self.partner_model.id,
                "view_id": view.id,
                "view_type": view_type,
                "anchor_kind": "view",
                "position": "attributes",
                "payload": {"attributes": attributes},
            }
        )

    def _root(self, view):
        return etree.fromstring(view.get_combined_arch())

    def test_hide_the_create_button_on_a_list(self):
        bundle = self._create_bundle(
            code="client_root_create",
            operations=[self._set_options(self.list_view, "list", {"create": "0"})],
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        self.assertEqual(self._root(self.list_view).get("create"), "0")

    def test_several_options_land_on_the_same_root(self):
        bundle = self._create_bundle(
            code="client_root_many",
            operations=[
                self._set_options(
                    self.list_view,
                    "list",
                    {"create": "0", "delete": "0", "editable": "bottom"},
                )
            ],
        )
        bundle.action_apply()
        root = self._root(self.list_view)
        self.assertEqual(root.get("create"), "0")
        self.assertEqual(root.get("delete"), "0")
        self.assertEqual(root.get("editable"), "bottom")

    def test_row_decoration_keeps_its_condition(self):
        bundle = self._create_bundle(
            code="client_root_decoration",
            operations=[
                self._set_options(
                    self.list_view,
                    "list",
                    {"decoration-danger": "company_type == 'person'"},
                )
            ],
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        self.assertEqual(
            self._root(self.list_view).get("decoration-danger"),
            "company_type == 'person'",
        )

    def test_an_empty_value_drops_the_option(self):
        editable_view = self.env["ir.ui.view"].create(
            {
                "name": "customization.tester.partner.list.editable",
                "model": "res.partner",
                "type": "list",
                "arch": """
                    <list editable="bottom">
                        <field name="name"/>
                    </list>
                """,
            }
        )
        bundle = self._create_bundle(
            code="client_root_drop",
            operations=[self._set_options(editable_view, "list", {"editable": ""})],
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        self.assertIsNone(self._root(editable_view).get("editable"))

    def test_dropping_the_bundle_restores_the_root(self):
        bundle = self._create_bundle(
            code="client_root_restore",
            operations=[self._set_options(self.list_view, "list", {"create": "0"})],
        )
        bundle.action_apply()
        bundle.operation_ids.unlink()
        self.assertIsNone(self._root(self.list_view).get("create"))

    def test_options_on_a_form_and_a_kanban(self):
        form_bundle = self._create_bundle(
            code="client_root_form",
            operations=[self._set_options(self.form_view, "form", {"delete": "0"})],
        )
        form_bundle.action_apply()
        self.assertEqual(self._root(self.form_view).get("delete"), "0")
        kanban_bundle = self._create_bundle(
            code="client_root_kanban",
            operations=[
                self._set_options(
                    self.kanban_view, "kanban", {"default_order": "name desc"}
                )
            ],
        )
        kanban_bundle.action_apply()
        self.assertEqual(self._root(self.kanban_view).get("default_order"), "name desc")

    def test_an_option_the_view_type_ignores_is_refused(self):
        bundle = self._create_bundle(
            code="client_root_wrong_type",
            operations=[
                self._set_options(self.form_view, "form", {"editable": "bottom"})
            ],
        )
        bundle.action_apply()
        operation = bundle.operation_ids
        self.assertEqual(operation.state, "broken")
        self.assertIn("editable", operation.broken_reason)

    def test_a_decoration_outside_a_list_is_refused(self):
        bundle = self._create_bundle(
            code="client_root_deco_form",
            operations=[
                self._set_options(self.form_view, "form", {"decoration-danger": "1"})
            ],
        )
        bundle.action_apply()
        self.assertIn("list", bundle.operation_ids.broken_reason)

    def test_an_unknown_decoration_is_refused(self):
        bundle = self._create_bundle(
            code="client_root_deco_unknown",
            operations=[
                self._set_options(self.list_view, "list", {"decoration-teal": "1"})
            ],
        )
        bundle.action_apply()
        self.assertIn("decoration", bundle.operation_ids.broken_reason)

    def test_a_broken_decoration_condition_is_refused(self):
        bundle = self._create_bundle(
            code="client_root_deco_syntax",
            operations=[
                self._set_options(
                    self.list_view, "list", {"decoration-danger": "state =="}
                )
            ],
        )
        bundle.action_apply()
        self.assertIn("Python", bundle.operation_ids.broken_reason)

    def test_a_boolean_option_refuses_a_free_value(self):
        bundle = self._create_bundle(
            code="client_root_bad_boolean",
            operations=[self._set_options(self.list_view, "list", {"create": "no"})],
        )
        bundle.action_apply()
        self.assertIn("0 or 1", bundle.operation_ids.broken_reason)

    def test_an_order_on_a_missing_field_is_refused(self):
        bundle = self._create_bundle(
            code="client_root_bad_order",
            operations=[
                self._set_options(
                    self.list_view, "list", {"default_order": "not_a_field"}
                )
            ],
        )
        bundle.action_apply()
        self.assertIn("not_a_field", bundle.operation_ids.broken_reason)

    def test_an_order_on_an_unstored_field_is_refused(self):
        bundle = self._create_bundle(
            code="client_root_unstored_order",
            operations=[
                self._set_options(
                    self.list_view, "list", {"default_order": "contact_address"}
                )
            ],
        )
        bundle.action_apply()
        self.assertIn("stored", bundle.operation_ids.broken_reason)

    def test_an_unknown_sort_direction_is_refused(self):
        bundle = self._create_bundle(
            code="client_root_bad_direction",
            operations=[
                self._set_options(
                    self.list_view, "list", {"default_order": "name upwards"}
                )
            ],
        )
        bundle.action_apply()
        self.assertIn("sort direction", bundle.operation_ids.broken_reason)

    def test_options_on_a_search_view_are_refused(self):
        bundle = self._create_bundle(
            code="client_root_search",
            operations=[self._set_options(self.search_view, "search", {"create": "0"})],
        )
        bundle.action_apply()
        self.assertIn("search", bundle.operation_ids.broken_reason)

    def test_options_on_a_pivot_view_are_refused(self):
        bundle = self._create_bundle(
            code="client_root_pivot",
            operations=[self._set_options(self.pivot_view, "pivot", {"create": "0"})],
        )
        bundle.action_apply()
        self.assertIn("pivot", bundle.operation_ids.broken_reason)

    def test_two_bundles_cannot_own_the_same_root(self):
        first = self._create_bundle(
            code="client_root_first",
            operations=[self._set_options(self.list_view, "list", {"create": "0"})],
        )
        first.action_apply()
        with self.assertRaises(ValidationError) as error:
            self._create_bundle(
                code="client_root_second",
                operations=[self._set_options(self.list_view, "list", {"edit": "0"})],
            )
        self.assertIn("client_root_first", str(error.exception))

    def test_the_ui_creates_the_operation_without_an_anchor_name(self):
        bundle = self._create_bundle(code="client_root_ui")
        self.env["customization.bundle"].create_from_ui(
            {
                "bundle_id": bundle.id,
                "action": "set_view_attribute",
                "model": "res.partner",
                "view_id": self.list_view.id,
                "view_type": "list",
                "anchor_kind": "view",
                "payload": {"attributes": {"create": "0"}},
                "apply": True,
            }
        )
        operation = bundle.operation_ids
        self.assertEqual(operation.type, "set_view_attribute")
        self.assertEqual(operation.state, "applied")
        self.assertEqual(self._root(self.list_view).get("create"), "0")

    def test_the_ui_refuses_view_options_on_a_node(self):
        bundle = self._create_bundle(code="client_root_ui_node")
        with self.assertRaises(UserError):
            self.env["customization.bundle"].create_from_ui(
                {
                    "bundle_id": bundle.id,
                    "action": "set_view_attribute",
                    "model": "res.partner",
                    "view_id": self.list_view.id,
                    "view_type": "list",
                    "anchor_name": "email",
                    "anchor_kind": "field",
                    "payload": {"attributes": {"create": "0"}},
                    "apply": True,
                }
            )

    def test_the_payload_text_round_trips(self):
        bundle = self._create_bundle(
            code="client_root_text",
            operations=[
                self._set_options(
                    self.list_view, "list", {"create": "0", "editable": "top"}
                )
            ],
        )
        operation = bundle.operation_ids
        self.assertEqual(operation.payload_attributes, "create=0\neditable=top")
        operation.payload_attributes = "create=1\ndelete=0"
        self.assertEqual(
            operation.payload["attributes"], {"create": "1", "delete": "0"}
        )
