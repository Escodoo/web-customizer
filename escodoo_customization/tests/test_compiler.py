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
