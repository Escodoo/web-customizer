# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.exceptions import AccessError, UserError, ValidationError
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
                    "name": "x_cust_ui_ref",
                },
                "apply": True,
            }
        )
        self.assertFalse(result["broken"])
        self.assertTrue(result["reload"])
        self.assertIn("x_cust_ui_ref", self.form_view.get_combined_arch())
        field = self.env["ir.model.fields"]._get("res.partner", "x_cust_ui_ref")
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
                    "name": "x_cust_vip_ui",
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
                "anchor_name": "x_cust_vip_ui",
                "payload": {
                    "ttype": "char",
                    "string": "Juvenal",
                    "name": "x_cust_juvenal_ui",
                },
                "apply": True,
            }
        )
        self.assertFalse(second["broken"])
        arch = self.form_view.get_combined_arch()
        self.assertIn("x_cust_vip_ui", arch)
        self.assertIn("x_cust_juvenal_ui", arch)

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
                    "name": "x_cust_ui_parent_email",
                    "related": "parent_id.email",
                },
                "apply": True,
            }
        )
        self.assertFalse(result["broken"])
        field = self.env["ir.model.fields"]._get(
            "res.partner", "x_cust_ui_parent_email"
        )
        self.assertEqual(field.related, "parent_id.email")
        self.assertEqual(field.ttype, "char")
        self.assertIn("x_cust_ui_parent_email", self.form_view.get_combined_arch())

    def test_create_from_ui_place_after_existing_field(self):
        bundle = self._create_bundle(code="client_ui_place")
        Field = self.env["ir.model.fields"]
        count_before = Field.search_count(
            [("model", "=", "res.partner"), ("name", "like", "x_cust_")]
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
                [("model", "=", "res.partner"), ("name", "like", "x_cust_")]
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
        group_ids = self.env["customization.bundle"].create_from_ui(
            {
                "bundle_id": bundle.id,
                "action": "set_groups",
                "model": "res.partner",
                "view_id": self.form_view.id,
                "view_type": "form",
                "anchor_name": "email",
                "payload": {
                    "group_ids": [self.env.ref("base.group_user").id],
                },
                "apply": True,
            }
        )
        self.assertFalse(group_ids["broken"])
        email_groups = bundle.operation_ids.filtered(
            lambda o: o.anchor_name == "email" and o.type == "set_groups"
        )
        self.assertEqual(email_groups.payload.get("groups"), "base.group_user")
        self.assertIn("base.group_user", self.form_view.get_combined_arch())
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
        with self.assertRaises(UserError):
            self.env["customization.bundle"].create_from_ui(
                {
                    "bundle_id": bundle.id,
                    "action": "set_groups",
                    "model": "res.partner",
                    "view_id": self.form_view.id,
                    "anchor_name": "email",
                    "payload": {"group_ids": []},
                }
            )
        orphan = self.env["res.groups"].create({"name": "No XML ID Group"})
        with self.assertRaises(UserError):
            self.env["customization.bundle"].create_from_ui(
                {
                    "bundle_id": bundle.id,
                    "action": "set_groups",
                    "model": "res.partner",
                    "view_id": self.form_view.id,
                    "anchor_name": "email",
                    "payload": {"group_ids": [orphan.id]},
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
        grouped = self._form_with_group()
        group = self.env["customization.bundle"].get_ui_context(
            grouped.id, "site_block", "group"
        )
        self.assertTrue(group["anchor_unique"])
        self.assertEqual(group["anchor_kind"], "group")

    def test_get_ui_context_lists_ambiguous_candidates(self):
        view = self.env["ir.ui.view"].create(
            {
                "name": "customization.tester.ui.ambiguous",
                "model": "res.partner",
                "type": "form",
                "arch": """
                    <form>
                        <field name="name"/>
                        <field name="email"/>
                        <notebook>
                            <page name="extra_info" string="Extra">
                                <field name="email"/>
                            </page>
                        </notebook>
                    </form>
                """,
            }
        )
        info = self.env["customization.bundle"].get_ui_context(view.id, "email")
        self.assertFalse(info["anchor_unique"])
        self.assertEqual(len(info["candidates"]), 2)
        self.assertEqual(info["candidates"][1]["index"], 1)
        self.assertEqual(info["candidates"][1]["page"], "extra_info")
        self.assertIn("page extra_info", info["candidates"][1]["label"])

    def test_create_from_ui_disambiguates_anchor(self):
        bundle = self._create_bundle(code="client_ui_ambiguous")
        view = self.env["ir.ui.view"].create(
            {
                "name": "customization.tester.ui.ambiguous.apply",
                "model": "res.partner",
                "type": "form",
                "arch": """
                    <form>
                        <field name="name"/>
                        <field name="email"/>
                        <field name="email"/>
                    </form>
                """,
            }
        )
        result = self.env["customization.bundle"].create_from_ui(
            {
                "bundle_id": bundle.id,
                "action": "hide",
                "model": "res.partner",
                "view_id": view.id,
                "view_type": "form",
                "anchor_name": "email",
                "anchor_index": 1,
                "apply": True,
            }
        )
        self.assertFalse(result["broken"])
        hide = bundle.operation_ids
        self.assertEqual(hide.anchor_occurrence, 2)
        self.assertIn("(//field[@name='email'])[2]", hide.generated_view_id.arch)

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
                    "name": "x_cust_ui_page_note",
                },
                "apply": True,
            }
        )
        self.assertFalse(result["broken"])
        place = bundle.operation_ids.filtered(lambda o: o.type == "place_field")
        self.assertEqual(place.anchor_kind, "page")
        self.assertEqual(place.position, "inside")
        self.assertIn("x_cust_ui_page_note", view.get_combined_arch())

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

    def test_create_from_ui_add_after_on_list(self):
        bundle = self._create_bundle(code="client_ui_list")
        result = self.env["customization.bundle"].create_from_ui(
            {
                "bundle_id": bundle.id,
                "action": "add_after",
                "model": "res.partner",
                "view_id": self.list_view.id,
                "view_type": "list",
                "anchor_name": "email",
                "payload": {
                    "ttype": "char",
                    "string": "List Reference",
                    "name": "x_cust_ui_list_ref",
                },
                "apply": True,
            }
        )
        self.assertFalse(result["broken"])
        self.assertIn("x_cust_ui_list_ref", self.list_view.get_combined_arch())

    def test_create_from_ui_hide_on_list(self):
        bundle = self._create_bundle(code="client_ui_list_hide")
        result = self.env["customization.bundle"].create_from_ui(
            {
                "bundle_id": bundle.id,
                "action": "hide",
                "model": "res.partner",
                "view_id": self.list_view.id,
                "view_type": "list",
                "anchor_name": "email",
                "apply": True,
            }
        )
        self.assertFalse(result["broken"])
        hide = bundle.operation_ids
        self.assertEqual(hide.view_type, "list")
        self.assertIn("column_invisible", hide.generated_view_id.arch)

    def test_create_from_ui_add_after_on_kanban(self):
        bundle = self._create_bundle(code="client_ui_kanban")
        result = self.env["customization.bundle"].create_from_ui(
            {
                "bundle_id": bundle.id,
                "action": "add_after",
                "model": "res.partner",
                "view_id": self.kanban_view.id,
                "view_type": "kanban",
                "anchor_name": "email",
                "payload": {
                    "ttype": "char",
                    "string": "Kanban Reference",
                    "name": "x_cust_ui_kanban_ref",
                },
                "apply": True,
            }
        )
        self.assertFalse(result["broken"])
        self.assertIn("x_cust_ui_kanban_ref", self.kanban_view.get_combined_arch())

    def test_create_from_ui_hide_on_kanban(self):
        bundle = self._create_bundle(code="client_ui_kanban_hide")
        result = self.env["customization.bundle"].create_from_ui(
            {
                "bundle_id": bundle.id,
                "action": "hide",
                "model": "res.partner",
                "view_id": self.kanban_view.id,
                "view_type": "kanban",
                "anchor_name": "email",
                "apply": True,
            }
        )
        self.assertFalse(result["broken"])
        hide = bundle.operation_ids
        self.assertEqual(hide.view_type, "kanban")
        self.assertIn("invisible", hide.generated_view_id.arch)
        self.assertNotIn("column_invisible", hide.generated_view_id.arch)

    def test_create_from_ui_hide_kanban_button(self):
        bundle = self._create_bundle(code="client_ui_kanban_button")
        result = self.env["customization.bundle"].create_from_ui(
            {
                "bundle_id": bundle.id,
                "action": "hide",
                "model": "res.partner",
                "view_id": self.kanban_view.id,
                "view_type": "kanban",
                "anchor_kind": "button",
                "anchor_name": "toggle_active",
                "apply": True,
            }
        )
        self.assertFalse(result["broken"])
        hide = bundle.operation_ids
        self.assertEqual(hide.anchor_kind, "button")
        self.assertEqual(hide.view_type, "kanban")
        self.assertIn(
            '<button name="toggle_active" position="attributes">',
            hide.generated_view_id.arch,
        )

    def test_create_from_ui_hide_kanban_header_button(self):
        bundle = self._create_bundle(code="client_ui_kanban_header")
        result = self.env["customization.bundle"].create_from_ui(
            {
                "bundle_id": bundle.id,
                "action": "hide",
                "model": "res.partner",
                "view_id": self.board_kanban_view.id,
                "view_type": "kanban",
                "anchor_kind": "button",
                "anchor_name": "toggle_active",
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

    def test_create_from_ui_hide_kanban_progressbar(self):
        bundle = self._create_bundle(code="client_ui_kanban_progress")
        result = self.env["customization.bundle"].create_from_ui(
            {
                "bundle_id": bundle.id,
                "action": "hide",
                "model": "res.partner",
                "view_id": self.board_kanban_view.id,
                "view_type": "kanban",
                "anchor_kind": "progressbar",
                "anchor_name": "company_type",
                "apply": True,
            }
        )
        self.assertFalse(result["broken"])
        hide = bundle.operation_ids
        self.assertEqual(hide.anchor_kind, "progressbar")
        self.assertIn(
            "expr=\"//progressbar[@field='company_type']\"",
            hide.generated_view_id.arch,
        )
        self.assertNotIn("progressbar", self.board_kanban_view.get_combined_arch())

    def test_create_from_ui_progressbar_rejects_rename(self):
        bundle = self._create_bundle(code="client_ui_kanban_progress_rename")
        with self.assertRaises(UserError):
            self.env["customization.bundle"].create_from_ui(
                {
                    "bundle_id": bundle.id,
                    "action": "rename",
                    "model": "res.partner",
                    "view_id": self.board_kanban_view.id,
                    "view_type": "kanban",
                    "anchor_kind": "progressbar",
                    "anchor_name": "company_type",
                    "payload": {"string": "Status"},
                    "apply": True,
                }
            )

    def test_create_from_ui_hide_kanban_button_type(self):
        bundle = self._create_bundle(code="client_ui_kanban_edit")
        result = self.env["customization.bundle"].create_from_ui(
            {
                "bundle_id": bundle.id,
                "action": "hide",
                "model": "res.partner",
                "view_id": self.kanban_view.id,
                "view_type": "kanban",
                "anchor_kind": "button",
                "anchor_name": "edit",
                "apply": True,
            }
        )
        self.assertFalse(result["broken"])
        self.assertIn(
            "expr=\"//button[@type='edit']\"",
            bundle.operation_ids.generated_view_id.arch,
        )

    def test_create_from_ui_add_after_on_search(self):
        bundle = self._create_bundle(code="client_ui_search")
        result = self.env["customization.bundle"].create_from_ui(
            {
                "bundle_id": bundle.id,
                "action": "add_after",
                "model": "res.partner",
                "view_id": self.search_view.id,
                "view_type": "search",
                "anchor_name": "email",
                "payload": {
                    "ttype": "char",
                    "string": "Search Reference",
                    "name": "x_cust_ui_search_ref",
                },
                "apply": True,
            }
        )
        self.assertFalse(result["broken"])
        self.assertIn("x_cust_ui_search_ref", self.search_view.get_combined_arch())

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

    def test_create_from_ui_add_page_after_page(self):
        bundle = self._create_bundle(code="client_ui_add_page")
        view = self._form_with_page()
        result = self.env["customization.bundle"].create_from_ui(
            {
                "bundle_id": bundle.id,
                "action": "add_page",
                "model": "res.partner",
                "view_id": view.id,
                "view_type": "form",
                "anchor_name": "extra_info",
                "anchor_kind": "page",
                "payload": {"string": "UI Page", "name": "x_cust_ui_page"},
                "apply": True,
            }
        )
        self.assertFalse(result["broken"])
        page = bundle.operation_ids
        self.assertEqual(page.type, "add_page")
        self.assertEqual(page.position, "after")
        self.assertIn("x_cust_ui_page", view.get_combined_arch())

    def test_create_from_ui_add_group_inside_page(self):
        bundle = self._create_bundle(code="client_ui_add_group")
        view = self._form_with_page()
        result = self.env["customization.bundle"].create_from_ui(
            {
                "bundle_id": bundle.id,
                "action": "add_group",
                "model": "res.partner",
                "view_id": view.id,
                "view_type": "form",
                "anchor_name": "extra_info",
                "anchor_kind": "page",
                "payload": {"string": "UI Group", "name": "x_cust_ui_group"},
                "apply": True,
            }
        )
        self.assertFalse(result["broken"])
        group = bundle.operation_ids
        self.assertEqual(group.type, "add_group")
        self.assertEqual(group.position, "inside")
        self.assertIn("x_cust_ui_group", view.get_combined_arch())

    def test_get_ui_context_unnamed_page(self):
        view = self._form_with_unnamed_page()
        info = self.env["customization.bundle"].get_ui_context(
            view.id, False, "page", "Field Service"
        )
        self.assertTrue(info["anchor_unique"])
        self.assertEqual(info["anchor_count"], 1)
        self.assertEqual(info["anchor_kind"], "page")

    def test_create_from_ui_add_group_inside_unnamed_page(self):
        bundle = self._create_bundle(code="client_ui_unnamed_page")
        view = self._form_with_unnamed_page()
        result = self.env["customization.bundle"].create_from_ui(
            {
                "bundle_id": bundle.id,
                "action": "add_group",
                "model": "res.partner",
                "view_id": view.id,
                "view_type": "form",
                "anchor_name": False,
                "anchor_kind": "page",
                "anchor_string": "Field Service",
                "payload": {"string": "UI FSM Group", "name": "x_cust_ui_fsm_group"},
                "apply": True,
            }
        )
        self.assertFalse(result["broken"])
        group = bundle.operation_ids
        self.assertFalse(group.anchor_name)
        self.assertEqual(group.anchor_string, "Field Service")
        self.assertEqual(group.position, "inside")
        self.assertIn(
            "//page[not(@name)][.//field[@name='phone']]",
            group.generated_view_id.arch,
        )
        self.assertIn("x_cust_ui_fsm_group", view.get_combined_arch())

    def test_create_from_ui_add_selection_field(self):
        bundle = self._create_bundle(code="client_ui_selection")
        result = self.env["customization.bundle"].create_from_ui(
            {
                "bundle_id": bundle.id,
                "action": "add_after",
                "model": "res.partner",
                "view_id": self.form_view.id,
                "view_type": "form",
                "anchor_name": "email",
                "payload": {
                    "ttype": "selection",
                    "string": "UI Status",
                    "name": "x_cust_ui_status",
                    "selection": [["open", "Open"], ["closed", "Closed"]],
                },
                "apply": True,
            }
        )
        self.assertFalse(result["broken"])
        field = self.env["ir.model.fields"]._get("res.partner", "x_cust_ui_status")
        self.assertEqual(field.ttype, "selection")
        self.assertIn("x_cust_ui_status", self.form_view.get_combined_arch())

    def test_create_from_ui_add_field_inside_named_group(self):
        bundle = self._create_bundle(code="client_ui_inside_group")
        view = self._form_with_group()
        result = self.env["customization.bundle"].create_from_ui(
            {
                "bundle_id": bundle.id,
                "action": "add_after",
                "model": "res.partner",
                "view_id": view.id,
                "view_type": "form",
                "anchor_name": "site_block",
                "anchor_kind": "group",
                "payload": {
                    "ttype": "char",
                    "string": "UI Group Note",
                    "name": "x_cust_ui_group_note",
                },
                "apply": True,
            }
        )
        self.assertFalse(result["broken"])
        place = bundle.operation_ids.filtered(lambda o: o.type == "place_field")
        self.assertEqual(place.anchor_kind, "group")
        self.assertEqual(place.position, "inside")
        self.assertIn(
            '<group name="site_block" position="inside">',
            place.generated_view_id.arch,
        )
        self.assertIn("x_cust_ui_group_note", view.get_combined_arch())

    def test_create_from_ui_add_field_inside_unnamed_group(self):
        bundle = self._create_bundle(code="client_ui_unnamed_group")
        view = self._form_with_group()
        result = self.env["customization.bundle"].create_from_ui(
            {
                "bundle_id": bundle.id,
                "action": "add_after",
                "model": "res.partner",
                "view_id": view.id,
                "view_type": "form",
                "anchor_name": False,
                "anchor_kind": "group",
                "anchor_string": "Notes",
                "payload": {
                    "ttype": "char",
                    "string": "UI Notes Extra",
                    "name": "x_cust_ui_notes_extra",
                },
                "apply": True,
            }
        )
        self.assertFalse(result["broken"])
        place = bundle.operation_ids.filtered(lambda o: o.type == "place_field")
        self.assertFalse(place.anchor_name)
        self.assertEqual(place.anchor_string, "Notes")
        self.assertEqual(place.position, "inside")
        self.assertIn("x_cust_ui_notes_extra", view.get_combined_arch())

    def test_create_from_ui_refuses_second_hide_on_same_field(self):
        bundle = self._create_bundle(code="client_ui_hide_owner")
        self.env["customization.bundle"].create_from_ui(
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
        other = self._create_bundle(code="client_ui_hide_intruder")
        with self.assertRaises(ValidationError) as error:
            self.env["customization.bundle"].create_from_ui(
                {
                    "bundle_id": other.id,
                    "action": "hide",
                    "model": "res.partner",
                    "view_id": self.form_view.id,
                    "view_type": "form",
                    "anchor_name": "phone",
                    "apply": True,
                }
            )
        self.assertIn("client_ui_hide_owner", str(error.exception))
