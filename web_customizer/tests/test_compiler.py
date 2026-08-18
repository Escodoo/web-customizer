# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from lxml import etree

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.web_customizer.hooks import uninstall_hook
from odoo.addons.web_customizer.models.compiler import (
    LEGACY_XMLID_MODULE,
    rebind_generated_xmlids,
)

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
            operations=self._ops_add_and_place("x_cust_site_ref", self.form_view),
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        field = self.env["ir.model.fields"]._get("res.partner", "x_cust_site_ref")
        self.assertTrue(field)
        self.assertEqual(field.ttype, "char")
        arch = self.form_view.get_combined_arch()
        self.assertIn('name="x_cust_site_ref"', arch)
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
                            "name": "x_cust_parent_email",
                            "related": "parent_id.email",
                        },
                    }
                ),
            ],
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        field = self.env["ir.model.fields"]._get("res.partner", "x_cust_parent_email")
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
                            "name": "x_cust_parent_country",
                            "related": "parent_id.country_id",
                            "store": True,
                        },
                    }
                ),
            ],
        )
        bundle.action_apply()
        field = self.env["ir.model.fields"]._get("res.partner", "x_cust_parent_country")
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
                            "name": "x_cust_bad_related",
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
                            "name": "x_cust_site_status",
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
                            "name": "x_cust_site_photo",
                        },
                    }
                ),
            ],
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        selection = self.env["ir.model.fields"]._get(
            "res.partner", "x_cust_site_status"
        )
        self.assertEqual(selection.ttype, "selection")
        self.assertEqual(
            selection.selection_ids.mapped("value"),
            ["draft", "done"],
        )
        binary = self.env["ir.model.fields"]._get("res.partner", "x_cust_site_photo")
        self.assertEqual(binary.ttype, "binary")

    def test_reapply_syncs_selection_options(self):
        bundle = self._create_bundle(
            code="client_sel_sync",
            operations=[
                Command.create(
                    {
                        "type": "add_field",
                        "sequence": 10,
                        "model_id": self.partner_model.id,
                        "payload": {
                            "ttype": "selection",
                            "string": "Site Status",
                            "name": "x_cust_sel_sync",
                            "selection": [["draft", "Draft"], ["done", "Done"]],
                        },
                    }
                )
            ],
        )
        bundle.action_apply()
        field = self.env["ir.model.fields"]._get("res.partner", "x_cust_sel_sync")
        field_id = field.id
        partner = self.env["res.partner"].create(
            {"name": "Sel Sync", "x_cust_sel_sync": "draft"}
        )
        operation = bundle.operation_ids
        operation.payload = {
            **operation.payload,
            "selection": [
                ["draft", "To Do"],
                ["done", "Done"],
                ["cancel", "Cancelled"],
            ],
        }
        bundle.action_reapply()
        field = self.env["ir.model.fields"]._get("res.partner", "x_cust_sel_sync")
        self.assertEqual(field.id, field_id)
        self.assertEqual(
            [(opt.value, opt.name) for opt in field.selection_ids.sorted("sequence")],
            [("draft", "To Do"), ("done", "Done"), ("cancel", "Cancelled")],
        )
        self.assertEqual(partner.x_cust_sel_sync, "draft")
        self.assertEqual(operation.state, "applied")

    def test_add_monetary_without_currency_is_broken(self):
        # res.partner carries currency_id as soon as accounting is around, so
        # the model has to be one nothing adds a currency to.
        model = self.env["ir.model"]._get("res.lang")
        bundle = self._create_bundle(
            code="client_monetary_bad",
            operations=[
                Command.create(
                    {
                        "type": "add_field",
                        "model_id": model.id,
                        "payload": {
                            "ttype": "monetary",
                            "string": "Site Amount",
                            "name": "x_cust_site_amount",
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
            operations=self._ops_add_and_place("x_cust_vip_flag", self.form_view)
            + [
                Command.create(
                    {
                        "type": "add_field",
                        "sequence": 30,
                        "model_id": self.partner_model.id,
                        "payload": {
                            "ttype": "char",
                            "string": "Site Code",
                            "name": "x_cust_site_code",
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
                        "anchor_name": "x_cust_vip_flag",
                        "position": "after",
                        "payload": {"field_name": "x_cust_site_code"},
                    }
                ),
            ],
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        arch = self.form_view.get_combined_arch()
        self.assertIn('name="x_cust_vip_flag"', arch)
        self.assertIn('name="x_cust_site_code"', arch)
        self.assertLess(
            arch.index('name="x_cust_vip_flag"'),
            arch.index('name="x_cust_site_code"'),
        )

    def test_health_check_marks_missing_anchor_broken(self):
        bundle = self._create_bundle(
            code="client_health",
            operations=self._ops_add_and_place("x_cust_health_ref", self.form_view)
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
            operations=self._ops_add_and_place("x_cust_reapply_ref", self.form_view),
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
        self.assertIn('name="x_cust_reapply_ref"', arch)

    def test_health_check_heals_restored_anchor(self):
        bundle = self._create_bundle(
            code="client_health_heal",
            operations=self._ops_add_and_place("x_cust_heal_ref", self.form_view),
        )
        bundle.action_apply()
        place = bundle.operation_ids.filtered(lambda o: o.type == "place_field")
        place.anchor_name = "missing_anchor"
        bundle.action_health_check()
        self.assertEqual(place.state, "broken")
        place.anchor_name = "email"
        bundle.action_health_check()
        self.assertEqual(place.state, "applied")
        self.assertFalse(place.broken_reason)
        self.assertTrue(place.generated_view_id.active)
        self.assertEqual(bundle.state, "applied")
        arch = self.form_view.get_combined_arch()
        self.assertIn('name="x_cust_heal_ref"', arch)

    def test_reapply_updates_add_field_metadata(self):
        bundle = self._create_bundle(
            code="client_field_meta",
            operations=[
                Command.create(
                    {
                        "type": "add_field",
                        "sequence": 10,
                        "model_id": self.partner_model.id,
                        "payload": {
                            "ttype": "char",
                            "string": "Old Label",
                            "name": "x_cust_meta_ref",
                            "help": "Old help",
                        },
                    }
                ),
            ],
        )
        bundle.action_apply()
        field = self.env["ir.model.fields"]._get("res.partner", "x_cust_meta_ref")
        field_id = field.id
        operation = bundle.operation_ids
        operation.payload = {
            **operation.payload,
            "string": "New Label",
            "help": "New help",
        }
        bundle.action_reapply()
        field = self.env["ir.model.fields"]._get("res.partner", "x_cust_meta_ref")
        self.assertEqual(field.id, field_id)
        self.assertEqual(field.ttype, "char")
        self.assertEqual(field.field_description, "New Label")
        self.assertEqual(field.help, "New help")

    def test_reapply_changes_add_field_ttype(self):
        bundle = self._create_bundle(
            code="client_ttype_evolve",
            operations=[
                Command.create(
                    {
                        "type": "add_field",
                        "sequence": 10,
                        "model_id": self.partner_model.id,
                        "payload": {
                            "ttype": "char",
                            "string": "Site Flag",
                            "name": "x_cust_site_flag",
                        },
                    }
                ),
            ],
        )
        bundle.action_apply()
        field = self.env["ir.model.fields"]._get("res.partner", "x_cust_site_flag")
        self.assertEqual(field.ttype, "char")
        field_id = field.id
        operation = bundle.operation_ids
        operation.payload = {
            **operation.payload,
            "ttype": "boolean",
            "string": "Site Flag",
            "name": "x_cust_site_flag",
        }
        bundle.action_reapply()
        field = self.env["ir.model.fields"]._get("res.partner", "x_cust_site_flag")
        self.assertTrue(field)
        self.assertEqual(field.ttype, "boolean")
        self.assertNotEqual(field.id, field_id)
        self.assertEqual(operation.generated_field_id, field)
        self.assertEqual(operation.state, "applied")
        self.assertEqual(bundle.state, "applied")

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

    def test_place_field_on_kanban_view(self):
        bundle = self._create_bundle(
            code="client_kanban",
            operations=self._ops_add_and_place(
                "x_cust_kanban_ref",
                self.kanban_view,
                view_type="kanban",
            ),
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        arch = self.kanban_view.get_combined_arch()
        self.assertIn('name="x_cust_kanban_ref"', arch)

    def test_hide_field_on_kanban_uses_invisible(self):
        bundle = self._create_bundle(
            code="client_kanban_hide",
            operations=[
                Command.create(
                    {
                        "type": "hide_field",
                        "sequence": 10,
                        "model_id": self.partner_model.id,
                        "view_id": self.kanban_view.id,
                        "view_type": "kanban",
                        "anchor_name": "email",
                        "payload": {},
                    }
                ),
            ],
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        arch = self.kanban_view.get_combined_arch()
        generated = bundle.operation_ids.generated_view_id.arch
        self.assertIn('invisible="True"', arch)
        self.assertNotIn("column_invisible", generated)

    def test_hide_named_kanban_button(self):
        bundle = self._create_bundle(
            code="client_kanban_button",
            operations=[
                Command.create(
                    {
                        "type": "hide_field",
                        "sequence": 10,
                        "model_id": self.partner_model.id,
                        "view_id": self.kanban_view.id,
                        "view_type": "kanban",
                        "anchor_kind": "button",
                        "anchor_name": "toggle_active",
                        "payload": {},
                    }
                ),
            ],
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        generated = bundle.operation_ids.generated_view_id.arch
        self.assertIn(
            '<button name="toggle_active" position="attributes">',
            generated,
        )
        self.assertIn('<attribute name="invisible">True</attribute>', generated)

    def test_hide_kanban_button_by_type(self):
        bundle = self._create_bundle(
            code="client_kanban_button_type",
            operations=[
                Command.create(
                    {
                        "type": "hide_field",
                        "sequence": 10,
                        "model_id": self.partner_model.id,
                        "view_id": self.kanban_view.id,
                        "view_type": "kanban",
                        "anchor_kind": "button",
                        "anchor_name": "edit",
                        "payload": {},
                    }
                ),
            ],
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        generated = bundle.operation_ids.generated_view_id.arch
        self.assertIn("expr=\"//button[@type='edit']\"", generated)
        self.assertIn('<attribute name="invisible">True</attribute>', generated)

    def test_hide_kanban_header_button(self):
        bundle = self._create_bundle(
            code="client_kanban_header",
            operations=[
                Command.create(
                    {
                        "type": "hide_field",
                        "sequence": 10,
                        "model_id": self.partner_model.id,
                        "view_id": self.board_kanban_view.id,
                        "view_type": "kanban",
                        "anchor_kind": "button",
                        "anchor_name": "toggle_active",
                        "payload": {},
                    }
                ),
            ],
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        generated = bundle.operation_ids.generated_view_id.arch
        self.assertIn(
            '<button name="toggle_active" position="attributes">',
            generated,
        )
        self.assertIn('<attribute name="invisible">True</attribute>', generated)

    def test_hide_kanban_progressbar(self):
        bundle = self._create_bundle(
            code="client_kanban_progress",
            operations=[
                Command.create(
                    {
                        "type": "hide_field",
                        "sequence": 10,
                        "model_id": self.partner_model.id,
                        "view_id": self.board_kanban_view.id,
                        "view_type": "kanban",
                        "anchor_kind": "progressbar",
                        "anchor_name": "company_type",
                        "payload": {},
                    }
                ),
            ],
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        generated = bundle.operation_ids.generated_view_id.arch
        self.assertIn("expr=\"//progressbar[@field='company_type']\"", generated)
        self.assertIn('position="replace"', generated)
        self.assertNotIn("progressbar", self.board_kanban_view.get_combined_arch())

    def test_place_field_on_search_view(self):
        bundle = self._create_bundle(
            code="client_search",
            operations=self._ops_add_and_place(
                "x_cust_search_ref",
                self.search_view,
                view_type="search",
            ),
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        arch = self.search_view.get_combined_arch()
        self.assertIn('name="x_cust_search_ref"', arch)

    def test_generated_xmlids_belong_to_bundle_code(self):
        bundle = self._create_bundle(
            code="client_xmlid_owner",
            operations=self._ops_add_and_place("x_cust_xmlid_ref", self.form_view),
        )
        bundle.action_apply()
        field = self.env["ir.model.fields"]._get("res.partner", "x_cust_xmlid_ref")
        place = bundle.operation_ids.filtered("generated_view_id")
        view = place.generated_view_id
        self.assertEqual(
            field.get_external_id().get(field.id),
            "client_xmlid_owner.field_res_partner_x_cust_xmlid_ref",
        )
        self.assertEqual(
            view.get_external_id().get(view.id),
            f"client_xmlid_owner.view_operation_{place.id}",
        )

    def test_rebind_migrates_legacy_ledger_xmlids(self):
        bundle = self._create_bundle(
            code="client_xmlid_rebind",
            operations=self._ops_add_and_place("x_cust_rebind_ref", self.form_view),
        )
        bundle.action_apply()
        place = bundle.operation_ids.filtered("generated_view_id")
        view = place.generated_view_id
        imd = self.env["ir.model.data"].search(
            [("model", "=", "ir.ui.view"), ("res_id", "=", view.id)],
            limit=1,
        )
        imd.write(
            {
                "module": LEGACY_XMLID_MODULE,
                "name": f"generated_view_{place.id}",
            }
        )
        rebind_generated_xmlids(self.env)
        self.assertEqual(imd.module, "client_xmlid_rebind")
        self.assertEqual(imd.name, f"view_operation_{place.id}")

    def test_uninstall_hook_keeps_generated_artifacts(self):
        bundle = self._create_bundle(
            code="client_uninstall",
            operations=self._ops_add_and_place("x_cust_uninstall_ref", self.form_view),
        )
        bundle.action_apply()
        field = self.env["ir.model.fields"]._get("res.partner", "x_cust_uninstall_ref")
        view = bundle.operation_ids.filtered("generated_view_id").generated_view_id
        field_id, view_id = field.id, view.id
        uninstall_hook(self.env)
        self.assertTrue(self.env["ir.model.fields"].browse(field_id).exists())
        self.assertTrue(self.env["ir.ui.view"].browse(view_id).exists())
        self.assertEqual(
            view.get_external_id().get(view.id).split(".", 1)[0],
            "client_uninstall",
        )

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
                            "name": "x_cust_page_note",
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
                        "payload": {"field_name": "x_cust_page_note"},
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
        self.assertIn("x_cust_page_note", view.get_combined_arch())

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
                            "name": "x_cust_site_notes",
                        },
                    }
                ),
            ],
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        generated = bundle.operation_ids.generated_view_id.arch
        self.assertIn('<page name="extra_info" position="after">', generated)
        self.assertIn('name="x_cust_site_notes"', generated)
        self.assertNotIn("<notebook>", generated)
        arch = view.get_combined_arch()
        self.assertIn("x_cust_site_notes", arch)
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
                        "payload": {"string": "Extra Tab", "name": "x_cust_extra_tab"},
                    }
                ),
            ],
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        generated = bundle.operation_ids.generated_view_id.arch
        self.assertIn("<notebook>", generated)
        self.assertIn('name="x_cust_extra_tab"', generated)
        self.assertIn("x_cust_extra_tab", self.form_view.get_combined_arch())

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
                            "name": "x_cust_site_group",
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
                            "name": "x_cust_page_group",
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
        self.assertIn("x_cust_site_group", arch)
        self.assertIn("x_cust_page_group", arch)

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
                            "name": "x_cust_fsm_group",
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
        self.assertIn("x_cust_fsm_group", view.get_combined_arch())

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
                            "name": "x_cust_site_note",
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
                        "payload": {"field_name": "x_cust_site_note"},
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
        self.assertIn("x_cust_site_note", view.get_combined_arch())

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
                            "name": "x_cust_extra_note",
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
                        "payload": {"field_name": "x_cust_extra_note"},
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
        self.assertIn("x_cust_extra_note", view.get_combined_arch())

    def test_second_bundle_cannot_hide_the_same_field(self):
        first = self._create_bundle(
            code="client_hide_owner",
            operations=[
                Command.create(
                    {
                        "type": "hide_field",
                        "model_id": self.partner_model.id,
                        "view_id": self.form_view.id,
                        "view_type": "form",
                        "anchor_name": "phone",
                        "payload": {},
                    }
                )
            ],
        )
        first.action_apply()
        with self.assertRaises(ValidationError) as error:
            self._create_bundle(
                code="client_hide_intruder",
                operations=[
                    Command.create(
                        {
                            "type": "hide_field",
                            "model_id": self.partner_model.id,
                            "view_id": self.form_view.id,
                            "view_type": "form",
                            "anchor_name": "phone",
                            "payload": {},
                        }
                    )
                ],
            )
        self.assertIn("client_hide_owner", str(error.exception))
        self.assertIn("Hide Field", str(error.exception))

    def test_hide_and_rename_same_field_can_coexist(self):
        hide = self._create_bundle(
            code="client_hide_phone_ok",
            operations=[
                Command.create(
                    {
                        "type": "hide_field",
                        "model_id": self.partner_model.id,
                        "view_id": self.form_view.id,
                        "view_type": "form",
                        "anchor_name": "phone",
                        "payload": {},
                    }
                )
            ],
        )
        rename = self._create_bundle(
            code="client_rename_phone_ok",
            operations=[
                Command.create(
                    {
                        "type": "set_string",
                        "model_id": self.partner_model.id,
                        "view_id": self.form_view.id,
                        "view_type": "form",
                        "anchor_name": "phone",
                        "payload": {"string": "Mobile"},
                    }
                )
            ],
        )
        hide.action_apply()
        rename.action_apply()
        arch = self.form_view.get_combined_arch()
        self.assertIn('invisible="True"', arch)
        self.assertIn('string="Mobile"', arch)

    def test_set_string_escapes_special_xml_characters(self):
        bundle = self._create_bundle(
            code="client_rename_amp",
            operations=[
                Command.create(
                    {
                        "type": "set_string",
                        "model_id": self.partner_model.id,
                        "view_id": self.form_view.id,
                        "view_type": "form",
                        "anchor_name": "email",
                        "payload": {"string": 'Sales & "Marketing"'},
                    }
                )
            ],
        )
        bundle.action_apply()
        operation = bundle.operation_ids
        self.assertEqual(operation.state, "applied")
        self.assertIn('Sales &amp; "Marketing"', operation.generated_view_id.arch)
        tree = etree.fromstring(self.form_view.get_combined_arch().encode())
        nodes = tree.xpath("//field[@name='email']")
        self.assertEqual(nodes[0].get("string"), 'Sales & "Marketing"')

    def test_set_string_escapes_apostrophe_in_page_name(self):
        view = self.env["ir.ui.view"].create(
            {
                "name": "customization.tester.apostrophe.page",
                "model": "res.partner",
                "type": "form",
                "arch": """
                    <form>
                        <sheet>
                            <notebook>
                                <page name="client's" string="Client">
                                    <field name="email"/>
                                </page>
                            </notebook>
                        </sheet>
                    </form>
                """,
            }
        )
        bundle = self._create_bundle(
            code="client_rename_page_apos",
            operations=[
                Command.create(
                    {
                        "type": "set_string",
                        "model_id": self.partner_model.id,
                        "view_id": view.id,
                        "view_type": "form",
                        "anchor_name": "email",
                        "anchor_page": "client's",
                        "payload": {"string": "Work Email"},
                    }
                )
            ],
        )
        bundle.action_apply()
        operation = bundle.operation_ids
        self.assertEqual(operation.state, "applied")
        tree = etree.fromstring(view.get_combined_arch().encode())
        nodes = tree.xpath("//field[@name='email']")
        self.assertEqual(nodes[0].get("string"), "Work Email")

    def test_unlink_releases_view_write_for_another_bundle(self):
        first = self._create_bundle(
            code="client_hide_release",
            operations=[
                Command.create(
                    {
                        "type": "hide_field",
                        "model_id": self.partner_model.id,
                        "view_id": self.form_view.id,
                        "view_type": "form",
                        "anchor_name": "phone",
                        "payload": {},
                    }
                )
            ],
        )
        first.action_apply()
        first.operation_ids.unlink()
        second = self._create_bundle(
            code="client_hide_takes_over",
            operations=[
                Command.create(
                    {
                        "type": "hide_field",
                        "model_id": self.partner_model.id,
                        "view_id": self.form_view.id,
                        "view_type": "form",
                        "anchor_name": "phone",
                        "payload": {},
                    }
                )
            ],
        )
        second.action_apply()
        self.assertEqual(second.operation_ids.state, "applied")
        self.assertIn("invisible", self.form_view.get_combined_arch())

    def test_broken_view_write_does_not_block_another_bundle(self):
        first = self._create_bundle(
            code="client_hide_stale",
            operations=[
                Command.create(
                    {
                        "type": "hide_field",
                        "model_id": self.partner_model.id,
                        "view_id": self.form_view.id,
                        "view_type": "form",
                        "anchor_name": "phone",
                        "payload": {},
                    }
                )
            ],
        )
        first.operation_ids.write(
            {"state": "broken", "broken_reason": "stale snapshot"}
        )
        second = self._create_bundle(
            code="client_hide_after_broken",
            operations=[
                Command.create(
                    {
                        "type": "hide_field",
                        "model_id": self.partner_model.id,
                        "view_id": self.form_view.id,
                        "view_type": "form",
                        "anchor_name": "phone",
                        "payload": {},
                    }
                )
            ],
        )
        second.action_apply()
        self.assertEqual(second.operation_ids.state, "applied")

    def test_second_bundle_cannot_place_the_same_field(self):
        first = self._create_bundle(
            code="client_place_owner",
            operations=self._ops_add_and_place("x_cust_place_once", self.form_view),
        )
        first.action_apply()
        with self.assertRaises(ValidationError) as error:
            self._create_bundle(
                code="client_place_intruder",
                operations=[
                    Command.create(
                        {
                            "type": "place_field",
                            "model_id": self.partner_model.id,
                            "view_id": self.form_view.id,
                            "view_type": "form",
                            "anchor_name": "phone",
                            "position": "after",
                            "payload": {"field_name": "x_cust_place_once"},
                        }
                    )
                ],
            )
        self.assertIn("client_place_owner", str(error.exception))
        self.assertIn("Place Field", str(error.exception))

    def test_place_same_field_on_form_and_list_can_coexist(self):
        form = self._create_bundle(
            code="client_place_form_ok",
            operations=self._ops_add_and_place("x_cust_place_both", self.form_view),
        )
        form.action_apply()
        listing = self._create_bundle(
            code="client_place_list_ok",
            operations=[
                Command.create(
                    {
                        "type": "place_field",
                        "model_id": self.partner_model.id,
                        "view_id": self.list_view.id,
                        "view_type": "list",
                        "anchor_name": "email",
                        "position": "after",
                        "payload": {"field_name": "x_cust_place_both"},
                    }
                )
            ],
        )
        listing.action_apply()
        self.assertEqual(listing.operation_ids.state, "applied")
        self.assertIn("x_cust_place_both", self.list_view.get_combined_arch())
