# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from lxml import etree

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import CustomizationCase


@tagged("post_install", "-at_install")
class TestCustomizationSubview(CustomizationCase):
    """Anchors inside the list an x2many field writes in its parent view."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bank_model = cls.env["ir.model"]._get("res.partner.bank")

    def _assert_applied(self, bundle):
        self.assertEqual(
            bundle.state, "applied", bundle.operation_ids.mapped("broken_reason")
        )

    def _root(self, view):
        return etree.fromstring(view.get_combined_arch())

    def _columns(self, view):
        root = self._root(view)
        nodes = root.xpath(".//field[@name='bank_ids']/list/field")
        return [node.get("name") for node in nodes]

    def _rename(self, view, anchor, string, subview="bank_ids"):
        return Command.create(
            {
                "type": "set_string",
                "model_id": self.bank_model.id,
                "view_id": view.id,
                "view_type": "list",
                "anchor_kind": "field",
                "anchor_name": anchor,
                "anchor_subview": subview,
                "position": "attributes",
                "payload": {"string": string},
            }
        )

    def test_place_a_column_inside_the_embedded_list(self):
        view = self._form_with_subview()
        bundle = self._create_bundle(
            code="client_sub_place",
            operations=[
                Command.create(
                    {
                        "type": "place_field",
                        "model_id": self.bank_model.id,
                        "view_id": view.id,
                        "view_type": "list",
                        "anchor_kind": "field",
                        "anchor_name": "acc_number",
                        "anchor_subview": "bank_ids",
                        "position": "after",
                        "payload": {"field_name": "bank_id"},
                    }
                )
            ],
        )
        bundle.action_apply()
        self._assert_applied(bundle)
        self.assertEqual(self._columns(view), ["acc_number", "bank_id", "company_id"])

    def test_a_shared_name_is_renamed_only_inside_the_subview(self):
        """The parent carries company_id too, so the scope has to hold."""
        view = self._form_with_subview()
        bundle = self._create_bundle(
            code="client_sub_scope",
            operations=[self._rename(view, "company_id", "Owning Company")],
        )
        bundle.action_apply()
        self._assert_applied(bundle)
        root = self._root(view)
        inner = root.xpath(".//field[@name='bank_ids']/list/field[@name='company_id']")
        outer = root.xpath(".//group/field[@name='company_id']")
        self.assertEqual(inner[0].get("string"), "Owning Company")
        self.assertFalse(outer[0].get("string"))

    def test_hide_a_column_of_the_embedded_list(self):
        view = self._form_with_subview()
        bundle = self._create_bundle(
            code="client_sub_hide",
            operations=[
                Command.create(
                    {
                        "type": "hide_field",
                        "model_id": self.bank_model.id,
                        "view_id": view.id,
                        "view_type": "list",
                        "anchor_kind": "field",
                        "anchor_name": "company_id",
                        "anchor_subview": "bank_ids",
                        "payload": {},
                    }
                )
            ],
        )
        bundle.action_apply()
        self._assert_applied(bundle)
        root = self._root(view)
        node = root.xpath(".//field[@name='bank_ids']/list/field[@name='company_id']")
        self.assertEqual(node[0].get("column_invisible"), "True")

    def test_make_the_embedded_list_editable(self):
        view = self._form_with_subview()
        bundle = self._create_bundle(
            code="client_sub_root",
            operations=[
                Command.create(
                    {
                        "type": "set_view_attribute",
                        "model_id": self.bank_model.id,
                        "view_id": view.id,
                        "view_type": "list",
                        "anchor_kind": "view",
                        "anchor_subview": "bank_ids",
                        "position": "attributes",
                        "payload": {"attributes": {"editable": "bottom"}},
                    }
                )
            ],
        )
        bundle.action_apply()
        self._assert_applied(bundle)
        root = self._root(view)
        node = root.xpath(".//field[@name='bank_ids']/list")
        self.assertEqual(node[0].get("editable"), "bottom")
        self.assertIsNone(root.get("editable"))

    def test_add_a_field_to_the_related_model(self):
        view = self._form_with_subview()
        bundle = self._create_bundle(
            code="client_sub_add",
            operations=[
                Command.create(
                    {
                        "type": "add_field",
                        "model_id": self.bank_model.id,
                        "payload": {
                            "name": "x_cust_note",
                            "ttype": "char",
                            "string": "Note",
                        },
                    }
                ),
                Command.create(
                    {
                        "type": "place_field",
                        "sequence": 20,
                        "model_id": self.bank_model.id,
                        "view_id": view.id,
                        "view_type": "list",
                        "anchor_kind": "field",
                        "anchor_name": "acc_number",
                        "anchor_subview": "bank_ids",
                        "position": "after",
                        "payload": {"field_name": "x_cust_note"},
                    }
                ),
            ],
        )
        bundle.action_apply()
        self._assert_applied(bundle)
        field = self.env["ir.model.fields"]._get("res.partner.bank", "x_cust_note")
        self.assertTrue(field)
        self.assertIn("x_cust_note", self._columns(view))

    def test_a_borrowed_list_is_refused_with_the_model_to_open(self):
        view = self._form_with_referenced_subview()
        bundle = self._create_bundle(
            code="client_sub_ref",
            operations=[self._rename(view, "acc_number", "Account")],
        )
        bundle.action_apply()
        operation = bundle.operation_ids
        self.assertEqual(operation.state, "broken")
        self.assertIn("res.partner.bank", operation.broken_reason)

    def test_an_anchor_on_a_field_that_holds_no_subview_is_refused(self):
        view = self._form_with_subview()
        bundle = self._create_bundle(
            code="client_sub_plain",
            operations=[self._rename(view, "acc_number", "Account", subview="name")],
        )
        bundle.action_apply()
        operation = bundle.operation_ids
        self.assertEqual(operation.state, "broken")
        self.assertIn("char", operation.broken_reason)

    def test_the_same_column_cannot_be_renamed_by_two_bundles(self):
        view = self._form_with_subview()
        self._create_bundle(
            code="client_sub_first",
            operations=[self._rename(view, "acc_number", "Account")],
        )
        with self.assertRaises(ValidationError):
            self._create_bundle(
                code="client_sub_second",
                operations=[self._rename(view, "acc_number", "Number")],
            )

    def test_a_card_field_of_a_written_kanban_is_an_anchor(self):
        view = self._form_with_kanban_subview()
        bundle = self._create_bundle(
            code="client_sub_kanban",
            operations=[
                Command.create(
                    {
                        "type": "set_string",
                        "model_id": self.bank_model.id,
                        "view_id": view.id,
                        "view_type": "kanban",
                        "anchor_kind": "field",
                        "anchor_name": "acc_number",
                        "anchor_subview": "bank_ids",
                        "position": "attributes",
                        "payload": {"string": "Account"},
                    }
                )
            ],
        )
        bundle.action_apply()
        self._assert_applied(bundle)
        root = self._root(view)
        node = root.xpath(
            ".//field[@name='bank_ids']/kanban//field[@name='acc_number']"
        )
        self.assertEqual(node[0].get("string"), "Account")

    def test_the_ui_reports_the_table_a_field_writes(self):
        view = self._form_with_subview()
        info = self.env["customization.bundle"].get_ui_context(
            view.id, "bank_ids", "field"
        )
        self.assertEqual(
            info["field_subview"], {"type": "list", "model": "res.partner.bank"}
        )

    def test_the_ui_reports_no_table_for_a_plain_field(self):
        view = self._form_with_subview()
        info = self.env["customization.bundle"].get_ui_context(view.id, "name", "field")
        self.assertFalse(info["field_subview"])

    def test_the_ui_reports_no_table_when_the_view_borrows_one(self):
        view = self._form_with_referenced_subview()
        info = self.env["customization.bundle"].get_ui_context(
            view.id, "bank_ids", "field"
        )
        self.assertFalse(info["field_subview"])

    def test_the_parent_and_the_subview_are_separate_scopes(self):
        """Same view, same name, different scope: no conflict."""
        view = self._form_with_subview()
        self._create_bundle(
            code="client_sub_inner",
            operations=[self._rename(view, "company_id", "Owning Company")],
        )
        bundle = self._create_bundle(
            code="client_sub_outer",
            operations=[
                Command.create(
                    {
                        "type": "set_string",
                        "model_id": self.partner_model.id,
                        "view_id": view.id,
                        "view_type": "form",
                        "anchor_kind": "field",
                        "anchor_name": "company_id",
                        "position": "attributes",
                        "payload": {"string": "Branch"},
                    }
                )
            ],
        )
        self.assertEqual(len(bundle.operation_ids), 1)
