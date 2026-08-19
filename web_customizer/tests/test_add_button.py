# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from lxml import etree

from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from ..models.exporter import export_bundle_files
from .common import CustomizationCase

ACTION_XMLID = "base.action_partner_form"


@tagged("post_install", "-at_install")
class TestCustomizationAddButton(CustomizationCase):
    """A button that calls an action already installed on the database."""

    def _give_form_an_xmlid(self):
        self.env["ir.model.data"].create(
            {
                "name": "tester_button_form",
                "module": "web_customizer",
                "model": "ir.ui.view",
                "res_id": self.form_view.id,
                "noupdate": True,
            }
        )

    def _assert_applied(self, bundle):
        self.assertEqual(
            bundle.state, "applied", bundle.operation_ids.mapped("broken_reason")
        )

    def _root(self, view):
        return etree.fromstring(view.get_combined_arch())

    def _button(self, view_id, anchor="name", payload=None, view_type="form"):
        vals = {
            "type": "add_button",
            "model_id": self.partner_model.id,
            "view_id": view_id,
            "view_type": view_type,
            "anchor_kind": "field",
            "anchor_name": anchor,
            "position": "after",
            "payload": payload
            or {"string": "Open Contacts", "action_xmlid": ACTION_XMLID},
        }
        return Command.create(vals)

    def test_button_calls_the_action_by_xmlid(self):
        bundle = self._create_bundle(
            code="button_form", operations=[self._button(self.form_view.id)]
        )
        bundle.action_apply()
        self._assert_applied(bundle)
        node = self._root(self.form_view).xpath(
            "//field[@name='name']/following-sibling::button[1]"
        )
        self.assertTrue(node)
        # The XML ID, not the database id: the button then survives a reinstall
        # of the module owning the action, and exports readable.
        self.assertEqual(node[0].get("name"), ACTION_XMLID)
        self.assertEqual(node[0].get("type"), "action")
        self.assertEqual(node[0].get("string"), "Open Contacts")

    def test_button_takes_a_style(self):
        bundle = self._create_bundle(
            code="button_style",
            operations=[
                self._button(
                    self.form_view.id,
                    payload={
                        "string": "Open",
                        "action_xmlid": ACTION_XMLID,
                        "btn_class": "btn-primary",
                    },
                )
            ],
        )
        bundle.action_apply()
        self._assert_applied(bundle)
        node = self._root(self.form_view).xpath("//button[@type='action']")
        self.assertEqual(node[0].get("class"), "btn-primary")

    def test_button_lands_on_a_list_column(self):
        bundle = self._create_bundle(
            code="button_list",
            operations=[
                self._button(self.list_view.id, anchor="email", view_type="list")
            ],
        )
        bundle.action_apply()
        self._assert_applied(bundle)
        node = self._root(self.list_view).xpath(
            "//field[@name='email']/following-sibling::button[1]"
        )
        self.assertEqual(node[0].get("name"), ACTION_XMLID)

    def test_button_next_to_a_header_button(self):
        view = self._form_with_page()
        bundle = self._create_bundle(
            code="button_header",
            operations=[
                Command.create(
                    {
                        "type": "add_button",
                        "model_id": self.partner_model.id,
                        "view_id": view.id,
                        "view_type": "form",
                        "anchor_kind": "button",
                        "anchor_name": "toggle_active",
                        "position": "after",
                        "payload": {
                            "string": "Open Contacts",
                            "action_xmlid": ACTION_XMLID,
                        },
                    }
                )
            ],
        )
        bundle.action_apply()
        self._assert_applied(bundle)
        node = self._root(view).xpath("//header/button[@type='action']")
        self.assertTrue(node)

    def test_button_inside_a_written_table(self):
        view = self._form_with_subview()
        bank_model = self.env["ir.model"]._get("res.partner.bank")
        bundle = self._create_bundle(
            code="button_subview",
            operations=[
                Command.create(
                    {
                        "type": "add_button",
                        "model_id": bank_model.id,
                        "view_id": view.id,
                        "view_type": "list",
                        "anchor_kind": "field",
                        "anchor_name": "acc_number",
                        "anchor_subview": "bank_ids",
                        "position": "after",
                        "payload": {
                            "string": "Open Contacts",
                            "action_xmlid": ACTION_XMLID,
                        },
                    }
                )
            ],
        )
        bundle.action_apply()
        self._assert_applied(bundle)
        node = self._root(view).xpath("//field[@name='bank_ids']/list/button")
        self.assertEqual(node[0].get("name"), ACTION_XMLID)

    def test_a_missing_action_is_refused(self):
        bundle = self._create_bundle(
            code="button_missing",
            operations=[
                self._button(
                    self.form_view.id,
                    payload={"string": "Open", "action_xmlid": "base.no_such_action"},
                )
            ],
        )
        bundle.action_apply()
        operation = bundle.operation_ids
        self.assertEqual(operation.state, "broken")
        self.assertIn("base.no_such_action", operation.broken_reason)

    def test_an_xmlid_that_is_not_an_action_is_refused(self):
        bundle = self._create_bundle(
            code="button_not_action",
            operations=[
                self._button(
                    self.form_view.id,
                    payload={"string": "Open", "action_xmlid": "base.main_company"},
                )
            ],
        )
        bundle.action_apply()
        self.assertEqual(bundle.operation_ids.state, "broken")
        self.assertIn("res.company", bundle.operation_ids.broken_reason)

    def test_a_button_without_a_label_is_refused(self):
        bundle = self._create_bundle(
            code="button_no_label",
            operations=[
                self._button(
                    self.form_view.id,
                    payload={"string": "", "action_xmlid": ACTION_XMLID},
                )
            ],
        )
        bundle.action_apply()
        self.assertEqual(bundle.operation_ids.state, "broken")

    def test_two_bundles_cannot_call_the_same_action_twice(self):
        first = self._create_bundle(
            code="button_first", operations=[self._button(self.form_view.id)]
        )
        first.action_apply()
        self._assert_applied(first)
        with self.assertRaises(ValidationError):
            self._create_bundle(
                code="button_second",
                operations=[self._button(self.form_view.id, anchor="email")],
            )

    def test_another_action_is_welcome_on_the_same_view(self):
        first = self._create_bundle(
            code="button_one", operations=[self._button(self.form_view.id)]
        )
        first.action_apply()
        second = self._create_bundle(
            code="button_two",
            operations=[
                self._button(
                    self.form_view.id,
                    anchor="email",
                    payload={
                        "string": "Open Companies",
                        "action_xmlid": "base.action_res_company_form",
                    },
                )
            ],
        )
        second.action_apply()
        self._assert_applied(second)
        self.assertEqual(len(self._root(self.form_view).xpath("//button")), 2)

    def test_the_ui_refuses_a_button_on_a_search_view(self):
        bundle = self._create_bundle(code="button_search")
        with self.assertRaises(UserError):
            self.env["customization.bundle"].create_from_ui(
                {
                    "bundle_id": bundle.id,
                    "action": "add_button",
                    "model": "res.partner",
                    "view_id": self.search_view.id,
                    "view_type": "search",
                    "anchor_kind": "field",
                    "anchor_name": "name",
                    "payload": {
                        "string": "Open",
                        "action_xmlid": ACTION_XMLID,
                    },
                }
            )

    def test_the_ui_creates_the_button_on_the_clicked_field(self):
        bundle = self._create_bundle(code="button_ui")
        self.env["customization.bundle"].create_from_ui(
            {
                "bundle_id": bundle.id,
                "action": "add_button",
                "model": "res.partner",
                "view_id": self.form_view.id,
                "view_type": "form",
                "anchor_kind": "field",
                "anchor_name": "email",
                "payload": {
                    "string": "Open Contacts",
                    "action_xmlid": ACTION_XMLID,
                    "btn_class": "btn-secondary",
                },
            }
        )
        self._assert_applied(bundle)
        operation = bundle.operation_ids
        self.assertEqual(operation.type, "add_button")
        self.assertEqual(operation.payload_btn_class, "btn-secondary")
        node = self._root(self.form_view).xpath(
            "//field[@name='email']/following-sibling::button[1]"
        )
        self.assertEqual(node[0].get("class"), "btn-secondary")

    def test_the_export_depends_on_the_module_owning_the_action(self):
        self._give_form_an_xmlid()
        bundle = self._create_bundle(
            code="button_export", operations=[self._button(self.form_view.id)]
        )
        bundle.action_apply()
        self._assert_applied(bundle)
        files = export_bundle_files(bundle)
        self.assertIn("'base'", files["__manifest__.py"])
        self.assertIn(ACTION_XMLID, files["views/inherited_views.xml"])
