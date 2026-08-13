# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import Command
from odoo.tests import tagged

from odoo.addons.escodoo_customization.hooks import uninstall_hook

from .common import CustomizationCase


@tagged("post_install", "-at_install")
class TestCustomizationCompiler(CustomizationCase):
    def _ops_add_and_place(self, field_name, view, view_type="form", anchor="email"):
        return [
            Command.create(
                {
                    "type": "add_field",
                    "sequence": 10,
                    "model_id": self.partner_model.id,
                    "payload": {
                        "ttype": "char",
                        "string": "Site Reference",
                        "name": field_name,
                    },
                }
            ),
            Command.create(
                {
                    "type": "place_field",
                    "sequence": 20,
                    "model_id": self.partner_model.id,
                    "view_id": view.id,
                    "view_type": view_type,
                    "anchor_name": anchor,
                    "position": "after",
                    "payload": {"field_name": field_name},
                }
            ),
        ]

    def test_add_and_place_field_on_form(self):
        bundle = self._create_bundle(
            code="client_place_form",
            operations=self._ops_add_and_place("x_esc_site_ref", self.form_view),
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        field = self.env["ir.model.fields"]._get("res.partner", "x_esc_site_ref")
        self.assertTrue(field)
        self.assertEqual(field.ttype, "char")
        arch = self.form_view.get_combined_arch()
        self.assertIn('name="x_esc_site_ref"', arch)
        self.assertIn('name="email"', arch)

    def test_add_related_field_infers_type(self):
        bundle = self._create_bundle(
            code="client_related",
            operations=[
                Command.create(
                    {
                        "type": "add_field",
                        "sequence": 10,
                        "model_id": self.partner_model.id,
                        "payload": {
                            "string": "Parent Email",
                            "name": "x_esc_parent_email",
                            "related": "parent_id.email",
                        },
                    }
                ),
            ],
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        field = self.env["ir.model.fields"]._get("res.partner", "x_esc_parent_email")
        self.assertTrue(field)
        self.assertEqual(field.ttype, "char")
        self.assertEqual(field.related, "parent_id.email")
        self.assertFalse(field.store)
        self.assertTrue(field.readonly)

    def test_add_related_stored_many2one(self):
        bundle = self._create_bundle(
            code="client_related_m2o",
            operations=[
                Command.create(
                    {
                        "type": "add_field",
                        "sequence": 10,
                        "model_id": self.partner_model.id,
                        "payload": {
                            "string": "Parent Country",
                            "name": "x_esc_parent_country",
                            "related": "parent_id.country_id",
                            "store": True,
                        },
                    }
                ),
            ],
        )
        bundle.action_apply()
        field = self.env["ir.model.fields"]._get("res.partner", "x_esc_parent_country")
        self.assertEqual(field.ttype, "many2one")
        self.assertEqual(field.relation, "res.country")
        self.assertTrue(field.store)

    def test_add_related_invalid_path_is_broken(self):
        bundle = self._create_bundle(
            code="client_related_bad",
            operations=[
                Command.create(
                    {
                        "type": "add_field",
                        "model_id": self.partner_model.id,
                        "payload": {
                            "string": "Broken Related",
                            "name": "x_esc_bad_related",
                            "related": "parent_id.no_such_field",
                        },
                    }
                ),
            ],
        )
        bundle.action_apply()
        operation = bundle.operation_ids
        self.assertEqual(operation.state, "broken")
        self.assertIn("no_such_field", operation.broken_reason)

    def test_add_selection_and_binary_fields(self):
        bundle = self._create_bundle(
            code="client_extra_ttypes",
            operations=[
                Command.create(
                    {
                        "type": "add_field",
                        "sequence": 10,
                        "model_id": self.partner_model.id,
                        "payload": {
                            "ttype": "selection",
                            "string": "Site Status",
                            "name": "x_esc_site_status",
                            "selection": [["draft", "Draft"], ["done", "Done"]],
                        },
                    }
                ),
                Command.create(
                    {
                        "type": "add_field",
                        "sequence": 20,
                        "model_id": self.partner_model.id,
                        "payload": {
                            "ttype": "binary",
                            "string": "Site Photo",
                            "name": "x_esc_site_photo",
                        },
                    }
                ),
            ],
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        selection = self.env["ir.model.fields"]._get("res.partner", "x_esc_site_status")
        self.assertEqual(selection.ttype, "selection")
        self.assertEqual(
            selection.selection_ids.mapped("value"),
            ["draft", "done"],
        )
        binary = self.env["ir.model.fields"]._get("res.partner", "x_esc_site_photo")
        self.assertEqual(binary.ttype, "binary")

    def test_add_monetary_without_currency_is_broken(self):
        bundle = self._create_bundle(
            code="client_monetary_bad",
            operations=[
                Command.create(
                    {
                        "type": "add_field",
                        "model_id": self.partner_model.id,
                        "payload": {
                            "ttype": "monetary",
                            "string": "Site Amount",
                            "name": "x_esc_site_amount",
                        },
                    }
                ),
            ],
        )
        bundle.action_apply()
        operation = bundle.operation_ids
        self.assertEqual(operation.state, "broken")
        self.assertIn("currency", operation.broken_reason)

    def test_place_field_after_custom_field_same_bundle(self):
        bundle = self._create_bundle(
            code="client_chain",
            operations=self._ops_add_and_place("x_esc_vip_flag", self.form_view)
            + [
                Command.create(
                    {
                        "type": "add_field",
                        "sequence": 30,
                        "model_id": self.partner_model.id,
                        "payload": {
                            "ttype": "char",
                            "string": "Site Code",
                            "name": "x_esc_site_code",
                        },
                    }
                ),
                Command.create(
                    {
                        "type": "place_field",
                        "sequence": 40,
                        "model_id": self.partner_model.id,
                        "view_id": self.form_view.id,
                        "view_type": "form",
                        "anchor_name": "x_esc_vip_flag",
                        "position": "after",
                        "payload": {"field_name": "x_esc_site_code"},
                    }
                ),
            ],
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        arch = self.form_view.get_combined_arch()
        self.assertIn('name="x_esc_vip_flag"', arch)
        self.assertIn('name="x_esc_site_code"', arch)
        self.assertLess(
            arch.index('name="x_esc_vip_flag"'),
            arch.index('name="x_esc_site_code"'),
        )

    def test_health_check_marks_missing_anchor_broken(self):
        bundle = self._create_bundle(
            code="client_health",
            operations=self._ops_add_and_place("x_esc_health_ref", self.form_view)
            + [
                Command.create(
                    {
                        "type": "place_field",
                        "sequence": 30,
                        "model_id": self.partner_model.id,
                        "view_id": self.form_view.id,
                        "view_type": "form",
                        "anchor_name": "phone",
                        "position": "after",
                        "payload": {"field_name": "comment"},
                    }
                ),
            ],
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        place_email = bundle.operation_ids.filtered(
            lambda o: o.anchor_name == "email" and o.type == "place_field"
        )
        place_phone = bundle.operation_ids.filtered(lambda o: o.anchor_name == "phone")
        place_email.anchor_name = "does_not_exist"
        bundle.action_health_check()
        self.assertEqual(place_email.state, "broken")
        self.assertTrue(place_email.broken_reason)
        self.assertEqual(place_phone.state, "applied")
        self.assertEqual(bundle.state, "needs_reapply")
        self.assertTrue(place_email.generated_view_id)
        self.assertFalse(place_email.generated_view_id.active)

    def test_reapply_restores_fixed_anchor(self):
        bundle = self._create_bundle(
            code="client_reapply",
            operations=self._ops_add_and_place("x_esc_reapply_ref", self.form_view),
        )
        bundle.action_apply()
        place = bundle.operation_ids.filtered(lambda o: o.type == "place_field")
        place.anchor_name = "missing_anchor"
        bundle.action_health_check()
        self.assertEqual(place.state, "broken")
        place.anchor_name = "email"
        bundle.action_reapply()
        self.assertEqual(place.state, "applied")
        self.assertFalse(place.broken_reason)
        self.assertTrue(place.generated_view_id.active)
        self.assertEqual(bundle.state, "applied")
        arch = self.form_view.get_combined_arch()
        self.assertIn('name="x_esc_reapply_ref"', arch)

    def test_place_field_sequence_is_stable(self):
        bundle = self._create_bundle(
            code="client_seq",
            operations=[
                Command.create(
                    {
                        "type": "place_field",
                        "sequence": 10,
                        "model_id": self.partner_model.id,
                        "view_id": self.form_view.id,
                        "view_type": "form",
                        "anchor_name": "email",
                        "position": "after",
                        "payload": {"field_name": "vat"},
                    }
                ),
                Command.create(
                    {
                        "type": "place_field",
                        "sequence": 20,
                        "model_id": self.partner_model.id,
                        "view_id": self.form_view.id,
                        "view_type": "form",
                        "anchor_name": "phone",
                        "position": "after",
                        "payload": {"field_name": "website"},
                    }
                ),
            ],
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        ops = bundle.operation_ids.sorted("sequence")
        self.assertEqual(ops[0].anchor_name, "email")
        self.assertEqual(ops[1].anchor_name, "phone")
        self.assertLessEqual(
            ops[0].generated_view_id.priority,
            ops[1].generated_view_id.priority,
        )

    def test_hide_field_form_vs_list(self):
        bundle = self._create_bundle(
            code="client_hide",
            operations=[
                Command.create(
                    {
                        "type": "hide_field",
                        "sequence": 10,
                        "model_id": self.partner_model.id,
                        "view_id": self.form_view.id,
                        "view_type": "form",
                        "anchor_name": "phone",
                        "payload": {},
                    }
                ),
                Command.create(
                    {
                        "type": "hide_field",
                        "sequence": 20,
                        "model_id": self.partner_model.id,
                        "view_id": self.list_view.id,
                        "view_type": "list",
                        "anchor_name": "email",
                        "payload": {},
                    }
                ),
            ],
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        form_arch = self.form_view.get_combined_arch()
        list_arch = self.list_view.get_combined_arch()
        self.assertIn('invisible="True"', form_arch)
        self.assertIn("column_invisible", list_arch)

    def test_missing_anchor_on_apply_is_broken_not_silent(self):
        bundle = self._create_bundle(
            code="client_missing",
            operations=[
                Command.create(
                    {
                        "type": "place_field",
                        "sequence": 10,
                        "model_id": self.partner_model.id,
                        "view_id": self.form_view.id,
                        "view_type": "form",
                        "anchor_name": "no_such_field",
                        "position": "after",
                        "payload": {"field_name": "email"},
                    }
                ),
            ],
        )
        bundle.action_apply()
        operation = bundle.operation_ids
        self.assertEqual(operation.state, "broken")
        self.assertIn("no_such_field", operation.broken_reason)
        self.assertEqual(bundle.state, "needs_reapply")

    def test_ambiguous_anchor_is_broken(self):
        ambiguous_view = self.env["ir.ui.view"].create(
            {
                "name": "customization.tester.ambiguous",
                "model": "res.partner",
                "type": "form",
                "arch": """
                    <form>
                        <field name="email"/>
                        <field name="email"/>
                    </form>
                """,
            }
        )
        bundle = self._create_bundle(
            code="client_ambiguous",
            operations=[
                Command.create(
                    {
                        "type": "place_field",
                        "model_id": self.partner_model.id,
                        "view_id": ambiguous_view.id,
                        "view_type": "form",
                        "anchor_name": "email",
                        "position": "after",
                        "payload": {"field_name": "phone"},
                    }
                ),
            ],
        )
        bundle.action_apply()
        self.assertEqual(bundle.operation_ids.state, "broken")
        self.assertIn("ambiguous", bundle.operation_ids.broken_reason)

    def test_ambiguous_anchor_with_index_applies(self):
        view = self.env["ir.ui.view"].create(
            {
                "name": "customization.tester.ambiguous.index",
                "model": "res.partner",
                "type": "form",
                "arch": """
                    <form>
                        <field name="name"/>
                        <field name="email"/>
                        <group>
                            <field name="email"/>
                        </group>
                    </form>
                """,
            }
        )
        bundle = self._create_bundle(
            code="client_ambiguous_index",
            operations=[
                Command.create(
                    {
                        "type": "place_field",
                        "model_id": self.partner_model.id,
                        "view_id": view.id,
                        "view_type": "form",
                        "anchor_name": "email",
                        "anchor_occurrence": 2,
                        "position": "after",
                        "payload": {"field_name": "phone"},
                    }
                ),
            ],
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        generated = bundle.operation_ids.generated_view_id.arch
        self.assertIn("(//field[@name='email'])[2]", generated)
        self.assertIn('name="phone"', view.get_combined_arch())

    def test_ambiguous_anchor_with_page_applies(self):
        view = self.env["ir.ui.view"].create(
            {
                "name": "customization.tester.ambiguous.page",
                "model": "res.partner",
                "type": "form",
                "arch": """
                    <form>
                        <notebook>
                            <page name="contact" string="Contact">
                                <field name="email"/>
                            </page>
                            <page name="extra_info" string="Extra">
                                <field name="email"/>
                            </page>
                        </notebook>
                    </form>
                """,
            }
        )
        bundle = self._create_bundle(
            code="client_ambiguous_page",
            operations=[
                Command.create(
                    {
                        "type": "place_field",
                        "model_id": self.partner_model.id,
                        "view_id": view.id,
                        "view_type": "form",
                        "anchor_name": "email",
                        "anchor_page": "extra_info",
                        "position": "after",
                        "payload": {"field_name": "phone"},
                    }
                ),
            ],
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        generated = bundle.operation_ids.generated_view_id.arch
        self.assertIn("//page[@name='extra_info']//field[@name='email']", generated)
        self.assertNotIn("(//field[@name='email'])", generated)

    def test_place_field_on_search_view(self):
        bundle = self._create_bundle(
            code="client_search",
            operations=self._ops_add_and_place(
                "x_esc_search_ref",
                self.search_view,
                view_type="search",
            ),
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        arch = self.search_view.get_combined_arch()
        self.assertIn('name="x_esc_search_ref"', arch)

    def test_uninstall_hook_removes_generated_artifacts(self):
        bundle = self._create_bundle(
            code="client_uninstall",
            operations=self._ops_add_and_place("x_esc_uninstall_ref", self.form_view),
        )
        bundle.action_apply()
        field = self.env["ir.model.fields"]._get("res.partner", "x_esc_uninstall_ref")
        view = bundle.operation_ids.filtered("generated_view_id").generated_view_id
        field_id, view_id = field.id, view.id
        uninstall_hook(self.env)
        self.assertFalse(self.env["ir.model.fields"].browse(field_id).exists())
        self.assertFalse(self.env["ir.ui.view"].browse(view_id).exists())

    def test_place_field_inside_named_page(self):
        view = self._form_with_page()
        bundle = self._create_bundle(
            code="client_page_inside",
            operations=[
                Command.create(
                    {
                        "type": "add_field",
                        "sequence": 10,
                        "model_id": self.partner_model.id,
                        "payload": {
                            "ttype": "char",
                            "string": "Page Note",
                            "name": "x_esc_page_note",
                        },
                    }
                ),
                Command.create(
                    {
                        "type": "place_field",
                        "sequence": 20,
                        "model_id": self.partner_model.id,
                        "view_id": view.id,
                        "view_type": "form",
                        "anchor_kind": "page",
                        "anchor_name": "extra_info",
                        "position": "inside",
                        "payload": {"field_name": "x_esc_page_note"},
                    }
                ),
            ],
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        place = bundle.operation_ids.filtered(lambda o: o.type == "place_field")
        self.assertIn(
            '<page name="extra_info" position="inside">',
            place.generated_view_id.arch,
        )
        self.assertIn("x_esc_page_note", view.get_combined_arch())

    def test_hide_named_page_and_button(self):
        view = self._form_with_page()
        bundle = self._create_bundle(
            code="client_page_button",
            operations=[
                Command.create(
                    {
                        "type": "hide_field",
                        "sequence": 10,
                        "model_id": self.partner_model.id,
                        "view_id": view.id,
                        "view_type": "form",
                        "anchor_kind": "page",
                        "anchor_name": "extra_info",
                        "payload": {},
                    }
                ),
                Command.create(
                    {
                        "type": "hide_field",
                        "sequence": 20,
                        "model_id": self.partner_model.id,
                        "view_id": view.id,
                        "view_type": "form",
                        "anchor_kind": "button",
                        "anchor_name": "toggle_active",
                        "payload": {},
                    }
                ),
            ],
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        arch = view.get_combined_arch()
        self.assertIn("invisible", arch)
        page_op = bundle.operation_ids.filtered(lambda o: o.anchor_kind == "page")
        button_op = bundle.operation_ids.filtered(lambda o: o.anchor_kind == "button")
        self.assertIn(
            '<page name="extra_info" position="attributes">',
            page_op.generated_view_id.arch,
        )
        self.assertIn(
            '<button name="toggle_active" position="attributes">',
            button_op.generated_view_id.arch,
        )

    def test_add_page_after_named_page(self):
        view = self._form_with_page()
        bundle = self._create_bundle(
            code="client_add_page",
            operations=[
                Command.create(
                    {
                        "type": "add_page",
                        "model_id": self.partner_model.id,
                        "view_id": view.id,
                        "view_type": "form",
                        "anchor_kind": "page",
                        "anchor_name": "extra_info",
                        "position": "after",
                        "payload": {
                            "string": "Site Notes",
                            "name": "x_esc_site_notes",
                        },
                    }
                ),
            ],
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        generated = bundle.operation_ids.generated_view_id.arch
        self.assertIn('<page name="extra_info" position="after">', generated)
        self.assertIn('name="x_esc_site_notes"', generated)
        self.assertNotIn("<notebook>", generated)
        arch = view.get_combined_arch()
        self.assertIn("x_esc_site_notes", arch)
        self.assertIn("Site Notes", arch)

    def test_add_page_after_field_wraps_notebook(self):
        bundle = self._create_bundle(
            code="client_add_page_field",
            operations=[
                Command.create(
                    {
                        "type": "add_page",
                        "model_id": self.partner_model.id,
                        "view_id": self.form_view.id,
                        "view_type": "form",
                        "anchor_name": "email",
                        "position": "after",
                        "payload": {"string": "Extra Tab", "name": "x_esc_extra_tab"},
                    }
                ),
            ],
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        generated = bundle.operation_ids.generated_view_id.arch
        self.assertIn("<notebook>", generated)
        self.assertIn('name="x_esc_extra_tab"', generated)
        self.assertIn("x_esc_extra_tab", self.form_view.get_combined_arch())

    def test_add_group_after_field_and_inside_page(self):
        view = self._form_with_page()
        bundle = self._create_bundle(
            code="client_add_group",
            operations=[
                Command.create(
                    {
                        "type": "add_group",
                        "sequence": 10,
                        "model_id": self.partner_model.id,
                        "view_id": view.id,
                        "view_type": "form",
                        "anchor_name": "email",
                        "position": "after",
                        "payload": {
                            "string": "Site Group",
                            "name": "x_esc_site_group",
                        },
                    }
                ),
                Command.create(
                    {
                        "type": "add_group",
                        "sequence": 20,
                        "model_id": self.partner_model.id,
                        "view_id": view.id,
                        "view_type": "form",
                        "anchor_kind": "page",
                        "anchor_name": "extra_info",
                        "position": "inside",
                        "payload": {
                            "string": "Page Group",
                            "name": "x_esc_page_group",
                        },
                    }
                ),
            ],
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        ops = bundle.operation_ids.sorted("sequence")
        self.assertIn(
            '<field name="email" position="after">',
            ops[0].generated_view_id.arch,
        )
        self.assertIn(
            '<page name="extra_info" position="inside">',
            ops[1].generated_view_id.arch,
        )
        arch = view.get_combined_arch()
        self.assertIn("x_esc_site_group", arch)
        self.assertIn("x_esc_page_group", arch)

    def test_add_group_inside_unnamed_page(self):
        view = self._form_with_unnamed_page()
        bundle = self._create_bundle(
            code="client_unnamed_page",
            operations=[
                Command.create(
                    {
                        "type": "add_group",
                        "sequence": 10,
                        "model_id": self.partner_model.id,
                        "view_id": view.id,
                        "view_type": "form",
                        "anchor_kind": "page",
                        "anchor_string": "Field Service",
                        "position": "inside",
                        "payload": {
                            "string": "Site Notes",
                            "name": "x_esc_fsm_group",
                        },
                    }
                ),
            ],
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        op = bundle.operation_ids
        self.assertIn(
            "//page[not(@name)][.//field[@name='phone']]",
            op.generated_view_id.arch,
        )
        self.assertIn("x_esc_fsm_group", view.get_combined_arch())

    def test_place_field_inside_named_group(self):
        view = self._form_with_group()
        bundle = self._create_bundle(
            code="client_inside_group",
            operations=[
                Command.create(
                    {
                        "type": "add_field",
                        "sequence": 10,
                        "model_id": self.partner_model.id,
                        "payload": {
                            "ttype": "char",
                            "string": "Site Note",
                            "name": "x_esc_site_note",
                        },
                    }
                ),
                Command.create(
                    {
                        "type": "place_field",
                        "sequence": 20,
                        "model_id": self.partner_model.id,
                        "view_id": view.id,
                        "view_type": "form",
                        "anchor_kind": "group",
                        "anchor_name": "site_block",
                        "position": "inside",
                        "payload": {"field_name": "x_esc_site_note"},
                    }
                ),
            ],
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        place = bundle.operation_ids.filtered(lambda o: o.type == "place_field")
        self.assertIn(
            '<group name="site_block" position="inside">',
            place.generated_view_id.arch,
        )
        self.assertIn("x_esc_site_note", view.get_combined_arch())

    def test_place_field_inside_unnamed_group(self):
        view = self._form_with_group()
        bundle = self._create_bundle(
            code="client_unnamed_group",
            operations=[
                Command.create(
                    {
                        "type": "add_field",
                        "sequence": 10,
                        "model_id": self.partner_model.id,
                        "payload": {
                            "ttype": "char",
                            "string": "Extra Note",
                            "name": "x_esc_extra_note",
                        },
                    }
                ),
                Command.create(
                    {
                        "type": "place_field",
                        "sequence": 20,
                        "model_id": self.partner_model.id,
                        "view_id": view.id,
                        "view_type": "form",
                        "anchor_kind": "group",
                        "anchor_string": "Notes",
                        "position": "inside",
                        "payload": {"field_name": "x_esc_extra_note"},
                    }
                ),
            ],
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        place = bundle.operation_ids.filtered(lambda o: o.type == "place_field")
        self.assertIn(
            "//group[not(@name)][.//field[@name='email']]",
            place.generated_view_id.arch,
        )
        self.assertIn("x_esc_extra_note", view.get_combined_arch())
