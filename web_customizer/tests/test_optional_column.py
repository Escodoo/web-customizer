# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from lxml import etree

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import CustomizationCase


@tagged("post_install", "-at_install")
class TestCustomizationOptionalColumn(CustomizationCase):
    """Only the list renderer builds a column picker from ``optional``."""

    def _set_optional(self, view, view_type, anchor, optional, anchor_kind="field"):
        return Command.create(
            {
                "type": "set_optional",
                "model_id": self.partner_model.id,
                "view_id": view.id,
                "view_type": view_type,
                "anchor_kind": anchor_kind,
                "anchor_name": anchor,
                "position": "attributes",
                "payload": {"optional": optional},
            }
        )

    def _column(self, view, name):
        tree = etree.fromstring(view.get_combined_arch())
        nodes = tree.xpath(f"//field[@name='{name}']")
        self.assertEqual(len(nodes), 1)
        return nodes[0]

    def test_hide_column_by_default(self):
        bundle = self._create_bundle(
            code="client_optional_hide",
            operations=[self._set_optional(self.list_view, "list", "email", "hide")],
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        self.assertEqual(self._column(self.list_view, "email").get("optional"), "hide")

    def test_show_column_by_default(self):
        bundle = self._create_bundle(
            code="client_optional_show",
            operations=[self._set_optional(self.list_view, "list", "email", "show")],
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        self.assertEqual(self._column(self.list_view, "email").get("optional"), "show")

    def test_optional_is_refused_outside_a_list(self):
        bundle = self._create_bundle(
            code="client_optional_form",
            operations=[self._set_optional(self.form_view, "form", "email", "hide")],
        )
        bundle.action_apply()
        operation = bundle.operation_ids
        self.assertEqual(operation.state, "broken")
        self.assertIn("list", operation.broken_reason)

    def test_unknown_optional_value_is_refused(self):
        bundle = self._create_bundle(
            code="client_optional_bad",
            operations=[self._set_optional(self.list_view, "list", "email", "maybe")],
        )
        bundle.action_apply()
        operation = bundle.operation_ids
        self.assertEqual(operation.state, "broken")
        self.assertIn("show", operation.broken_reason)

    def test_two_bundles_cannot_own_the_same_column(self):
        first = self._create_bundle(
            code="client_optional_first",
            operations=[self._set_optional(self.list_view, "list", "email", "hide")],
        )
        first.action_apply()
        with self.assertRaises(ValidationError) as error:
            self._create_bundle(
                code="client_optional_second",
                operations=[
                    self._set_optional(self.list_view, "list", "email", "show")
                ],
            )
        self.assertIn("client_optional_first", str(error.exception))

    def test_optional_from_the_ui_creates_the_operation(self):
        bundle = self._create_bundle(code="client_optional_ui")
        self.env["customization.bundle"].create_from_ui(
            {
                "bundle_id": bundle.id,
                "action": "set_optional",
                "model": "res.partner",
                "view_id": self.list_view.id,
                "view_type": "list",
                "anchor_name": "email",
                "anchor_kind": "field",
                "payload": {"optional": "hide"},
                "apply": True,
            }
        )
        operation = bundle.operation_ids
        self.assertEqual(operation.type, "set_optional")
        self.assertEqual(operation.state, "applied")
        self.assertEqual(self._column(self.list_view, "email").get("optional"), "hide")
