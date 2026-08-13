# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import CustomizationCase


@tagged("post_install", "-at_install")
class TestCustomizationUiApi(CustomizationCase):
    def test_create_from_ui_add_after(self):
        bundle = self._create_bundle(code="client_ui_add")
        result = self.env["customization.bundle"].create_from_ui(
            {
                "bundle_id": bundle.id,
                "action": "add_after",
                "model": "res.partner",
                "view_id": self.form_view.id,
                "view_type": "form",
                "anchor_name": "email",
                "payload": {
                    "ttype": "char",
                    "string": "Site Reference",
                    "name": "x_esc_ui_ref",
                },
                "apply": True,
            }
        )
        self.assertFalse(result["broken"])
        self.assertTrue(result["reload"])
        self.assertIn("x_esc_ui_ref", self.form_view.get_combined_arch())
        field = self.env["ir.model.fields"]._get("res.partner", "x_esc_ui_ref")
        self.assertTrue(field)

    def test_create_from_ui_hide_and_rename(self):
        bundle = self._create_bundle(code="client_ui_attrs")
        hide = self.env["customization.bundle"].create_from_ui(
            {
                "bundle_id": bundle.id,
                "action": "hide",
                "model": "res.partner",
                "view_id": self.form_view.id,
                "view_type": "form",
                "anchor_name": "phone",
                "apply": True,
            }
        )
        self.assertFalse(hide["broken"])
        self.assertIn("invisible", self.form_view.get_combined_arch())
        rename = self.env["customization.bundle"].create_from_ui(
            {
                "bundle_id": bundle.id,
                "action": "rename",
                "model": "res.partner",
                "view_id": self.form_view.id,
                "view_type": "form",
                "anchor_name": "email",
                "payload": {"string": "Work Email"},
                "apply": True,
            }
        )
        self.assertFalse(rename["broken"])
        self.assertIn("Work Email", self.form_view.get_combined_arch())

    def test_get_ui_context_reports_unique_anchor(self):
        info = self.env["customization.bundle"].get_ui_context(
            self.form_view.id, "email"
        )
        self.assertTrue(info["anchor_unique"])
        self.assertEqual(info["anchor_count"], 1)
        missing = self.env["customization.bundle"].get_ui_context(
            self.form_view.id, "does_not_exist"
        )
        self.assertFalse(missing["anchor_unique"])
        self.assertEqual(missing["anchor_count"], 0)

    def test_create_from_ui_requires_manager(self):
        bundle = self._create_bundle(code="client_ui_acl")
        user = self.env["res.users"].create(
            {
                "name": "No Manager",
                "login": "esc_cust_nomgr",
                "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )
        with self.assertRaises(AccessError):
            self.env["customization.bundle"].with_user(user).create_from_ui(
                {
                    "bundle_id": bundle.id,
                    "action": "hide",
                    "model": "res.partner",
                    "view_id": self.form_view.id,
                    "anchor_name": "email",
                }
            )

    def test_create_from_ui_requires_bundle(self):
        with self.assertRaises(UserError):
            self.env["customization.bundle"].create_from_ui(
                {
                    "action": "hide",
                    "model": "res.partner",
                    "view_id": self.form_view.id,
                    "anchor_name": "email",
                }
            )
