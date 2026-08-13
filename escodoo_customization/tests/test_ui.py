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

    def test_create_from_ui_add_after_custom_field(self):
        bundle = self._create_bundle(code="client_ui_chain")
        first = self.env["customization.bundle"].create_from_ui(
            {
                "bundle_id": bundle.id,
                "action": "add_after",
                "model": "res.partner",
                "view_id": self.form_view.id,
                "view_type": "form",
                "anchor_name": "email",
                "payload": {
                    "ttype": "boolean",
                    "string": "VIP Customer",
                    "name": "x_esc_vip_ui",
                },
                "apply": True,
            }
        )
        self.assertFalse(first["broken"])
        second = self.env["customization.bundle"].create_from_ui(
            {
                "bundle_id": bundle.id,
                "action": "add_after",
                "model": "res.partner",
                "view_id": self.form_view.id,
                "view_type": "form",
                "anchor_name": "x_esc_vip_ui",
                "payload": {
                    "ttype": "char",
                    "string": "Juvenal",
                    "name": "x_esc_juvenal_ui",
                },
                "apply": True,
            }
        )
        self.assertFalse(second["broken"])
        arch = self.form_view.get_combined_arch()
        self.assertIn("x_esc_vip_ui", arch)
        self.assertIn("x_esc_juvenal_ui", arch)

    def test_create_from_ui_add_related_field(self):
        bundle = self._create_bundle(code="client_ui_related")
        result = self.env["customization.bundle"].create_from_ui(
            {
                "bundle_id": bundle.id,
                "action": "add_after",
                "model": "res.partner",
                "view_id": self.form_view.id,
                "view_type": "form",
                "anchor_name": "email",
                "payload": {
                    "string": "Parent Email",
                    "name": "x_esc_ui_parent_email",
                    "related": "parent_id.email",
                },
                "apply": True,
            }
        )
        self.assertFalse(result["broken"])
        field = self.env["ir.model.fields"]._get("res.partner", "x_esc_ui_parent_email")
        self.assertEqual(field.related, "parent_id.email")
        self.assertEqual(field.ttype, "char")
        self.assertIn("x_esc_ui_parent_email", self.form_view.get_combined_arch())

    def test_create_from_ui_place_after_existing_field(self):
        bundle = self._create_bundle(code="client_ui_place")
        Field = self.env["ir.model.fields"]
        count_before = Field.search_count(
            [("model", "=", "res.partner"), ("name", "like", "x_esc_")]
        )
        result = self.env["customization.bundle"].create_from_ui(
            {
                "bundle_id": bundle.id,
                "action": "place_after",
                "model": "res.partner",
                "view_id": self.form_view.id,
                "view_type": "form",
                "anchor_name": "email",
                "payload": {"field_name": "vat"},
                "apply": True,
            }
        )
        self.assertFalse(result["broken"])
        arch = self.form_view.get_combined_arch()
        self.assertIn('name="vat"', arch)
        self.assertLess(arch.index('name="email"'), arch.index('name="vat"'))
        self.assertEqual(
            Field.search_count(
                [("model", "=", "res.partner"), ("name", "like", "x_esc_")]
            ),
            count_before,
        )
        self.assertEqual(len(bundle.operation_ids), 1)
        self.assertEqual(bundle.operation_ids.type, "place_field")

    def test_create_from_ui_place_after_requires_existing_field(self):
        bundle = self._create_bundle(code="client_ui_place_missing")
        with self.assertRaises(UserError):
            self.env["customization.bundle"].create_from_ui(
                {
                    "bundle_id": bundle.id,
                    "action": "place_after",
                    "model": "res.partner",
                    "view_id": self.form_view.id,
                    "anchor_name": "email",
                    "payload": {"field_name": "does_not_exist"},
                }
            )
        with self.assertRaises(UserError):
            self.env["customization.bundle"].create_from_ui(
                {
                    "bundle_id": bundle.id,
                    "action": "place_after",
                    "model": "res.partner",
                    "view_id": self.form_view.id,
                    "anchor_name": "email",
                    "payload": {"field_name": "email"},
                }
            )

    def test_create_from_ui_set_widget_groups_and_modifiers(self):
        bundle = self._create_bundle(code="client_ui_attrs_extra")
        widget = self.env["customization.bundle"].create_from_ui(
            {
                "bundle_id": bundle.id,
                "action": "set_widget",
                "model": "res.partner",
                "view_id": self.form_view.id,
                "view_type": "form",
                "anchor_name": "email",
                "payload": {"widget": "email"},
                "apply": True,
            }
        )
        self.assertFalse(widget["broken"])
        arch = self.form_view.get_combined_arch()
        self.assertIn('widget="email"', arch)
        groups = self.env["customization.bundle"].create_from_ui(
            {
                "bundle_id": bundle.id,
                "action": "set_groups",
                "model": "res.partner",
                "view_id": self.form_view.id,
                "view_type": "form",
                "anchor_name": "phone",
                "payload": {"groups": "base.group_system"},
                "apply": True,
            }
        )
        self.assertFalse(groups["broken"])
        self.assertIn("base.group_system", self.form_view.get_combined_arch())
        modifiers = self.env["customization.bundle"].create_from_ui(
            {
                "bundle_id": bundle.id,
                "action": "set_modifier",
                "model": "res.partner",
                "view_id": self.form_view.id,
                "view_type": "form",
                "anchor_name": "name",
                "payload": {"modifiers": {"readonly": "True", "required": True}},
                "apply": True,
            }
        )
        self.assertFalse(modifiers["broken"])
        arch = self.form_view.get_combined_arch()
        self.assertIn('readonly="True"', arch)
        self.assertIn('required="True"', arch)
        self.assertEqual(
            bundle.operation_ids.filtered(lambda o: o.type == "set_modifier").payload[
                "modifiers"
            ],
            {"readonly": "True", "required": "True"},
        )

    def test_create_from_ui_set_modifier_requires_value(self):
        bundle = self._create_bundle(code="client_ui_mod_empty")
        with self.assertRaises(UserError):
            self.env["customization.bundle"].create_from_ui(
                {
                    "bundle_id": bundle.id,
                    "action": "set_modifier",
                    "model": "res.partner",
                    "view_id": self.form_view.id,
                    "anchor_name": "email",
                    "payload": {"modifiers": {"invisible": "  "}},
                }
            )
        with self.assertRaises(UserError):
            self.env["customization.bundle"].create_from_ui(
                {
                    "bundle_id": bundle.id,
                    "action": "set_widget",
                    "model": "res.partner",
                    "view_id": self.form_view.id,
                    "anchor_name": "email",
                    "payload": {"widget": ""},
                }
            )

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
        view = self._form_with_page()
        page = self.env["customization.bundle"].get_ui_context(
            view.id, "extra_info", "page"
        )
        self.assertTrue(page["anchor_unique"])
        self.assertEqual(page["anchor_kind"], "page")
        button = self.env["customization.bundle"].get_ui_context(
            view.id, "toggle_active", "button"
        )
        self.assertTrue(button["anchor_unique"])

    def test_create_from_ui_add_field_inside_page(self):
        bundle = self._create_bundle(code="client_ui_page")
        view = self._form_with_page()
        result = self.env["customization.bundle"].create_from_ui(
            {
                "bundle_id": bundle.id,
                "action": "add_after",
                "model": "res.partner",
                "view_id": view.id,
                "view_type": "form",
                "anchor_name": "extra_info",
                "anchor_kind": "page",
                "payload": {
                    "ttype": "char",
                    "string": "Page Note",
                    "name": "x_esc_ui_page_note",
                },
                "apply": True,
            }
        )
        self.assertFalse(result["broken"])
        place = bundle.operation_ids.filtered(lambda o: o.type == "place_field")
        self.assertEqual(place.anchor_kind, "page")
        self.assertEqual(place.position, "inside")
        self.assertIn("x_esc_ui_page_note", view.get_combined_arch())

    def test_create_from_ui_hide_button(self):
        bundle = self._create_bundle(code="client_ui_button")
        view = self._form_with_page()
        result = self.env["customization.bundle"].create_from_ui(
            {
                "bundle_id": bundle.id,
                "action": "hide",
                "model": "res.partner",
                "view_id": view.id,
                "view_type": "form",
                "anchor_name": "toggle_active",
                "anchor_kind": "button",
                "apply": True,
            }
        )
        self.assertFalse(result["broken"])
        hide = bundle.operation_ids
        self.assertEqual(hide.anchor_kind, "button")
        self.assertIn(
            '<button name="toggle_active" position="attributes">',
            hide.generated_view_id.arch,
        )

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
