# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import json

from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from odoo.addons.web_customizer.models.exporter import export_bundle_files

from .common import CustomizationCase


@tagged("post_install", "-at_install")
class TestCustomizationSetDefault(CustomizationCase):
    """A global ir.default compiled from a set_default ledger operation."""

    def _assert_applied(self, bundle):
        self.assertEqual(
            bundle.state, "applied", bundle.operation_ids.mapped("broken_reason")
        )

    def _global_default(self, model, field_name):
        field = self.env["ir.model.fields"]._get(model, field_name)
        return self.env["ir.default"].search(
            [
                ("field_id", "=", field.id),
                ("user_id", "=", False),
                ("company_id", "=", False),
                ("condition", "=", False),
            ],
            limit=1,
        )

    def _set_default_op(self, field_name, value=None, value_xmlid=None, **extra):
        payload = {"field_name": field_name}
        if value_xmlid:
            payload["value_xmlid"] = value_xmlid
        elif value is not None:
            payload["value"] = value
        vals = {
            "type": "set_default",
            "model_id": self.partner_model.id,
            "payload": payload,
        }
        vals.update(extra)
        return Command.create(vals)

    def test_sets_a_char_default(self):
        bundle = self._create_bundle(
            code="client_default_char",
            operations=[self._set_default_op("email", "site@example.com")],
        )
        bundle.action_apply()
        self._assert_applied(bundle)
        operation = bundle.operation_ids
        self.assertTrue(operation.generated_default_id)
        self.assertEqual(
            json.loads(operation.generated_default_id.json_value), "site@example.com"
        )
        self.assertEqual(
            self.env["res.partner"].default_get(["email"])["email"],
            "site@example.com",
        )

    def test_sets_a_many2one_default_from_xmlid(self):
        company = self.env.ref("base.main_company")
        bundle = self._create_bundle(
            code="client_default_m2o",
            operations=[
                self._set_default_op("company_id", value_xmlid="base.main_company")
            ],
        )
        bundle.action_apply()
        self._assert_applied(bundle)
        default = bundle.operation_ids.generated_default_id
        self.assertEqual(json.loads(default.json_value), company.id)
        self.assertEqual(
            bundle.operation_ids.payload.get("value_xmlid"), "base.main_company"
        )

    def test_invalid_value_marks_the_operation_broken(self):
        bundle = self._create_bundle(
            code="client_default_bad",
            operations=[self._set_default_op("color", "not-a-number")],
        )
        bundle.action_apply()
        operation = bundle.operation_ids
        self.assertEqual(operation.state, "broken")
        self.assertTrue(operation.broken_reason)
        self.assertFalse(operation.generated_default_id)

    def test_related_field_is_refused(self):
        bundle = self._create_bundle(
            code="client_default_related",
            operations=[self._set_default_op("country_code", "BR")],
        )
        bundle.action_apply()
        operation = bundle.operation_ids
        self.assertEqual(operation.state, "broken")
        self.assertIn("ignores defaults", operation.broken_reason)

    def test_second_bundle_cannot_set_the_same_field(self):
        first = self._create_bundle(
            code="client_default_owner",
            operations=[self._set_default_op("email", "first@example.com")],
        )
        first.action_apply()
        self._assert_applied(first)
        with self.assertRaises(ValidationError) as error:
            self._create_bundle(
                code="client_default_intruder",
                operations=[self._set_default_op("email", "second@example.com")],
            )
        self.assertIn("client_default_owner", str(error.exception))

    def test_unlink_restores_the_native_default(self):
        self.env["ir.default"].set("res.partner", "email", "native@example.com")
        native = self._global_default("res.partner", "email")
        self.assertTrue(native)
        bundle = self._create_bundle(
            code="client_default_restore",
            operations=[self._set_default_op("email", "custom@example.com")],
        )
        bundle.action_apply()
        self._assert_applied(bundle)
        self.assertEqual(json.loads(native.json_value), "custom@example.com")
        bundle.unlink()
        restored = self._global_default("res.partner", "email")
        self.assertTrue(restored)
        self.assertEqual(json.loads(restored.json_value), "native@example.com")

    def test_unlink_drops_a_default_this_bundle_created(self):
        existing = self._global_default("res.partner", "website")
        if existing:
            existing.unlink()
        bundle = self._create_bundle(
            code="client_default_drop",
            operations=[self._set_default_op("website", "https://example.com")],
        )
        bundle.action_apply()
        self._assert_applied(bundle)
        default_id = bundle.operation_ids.generated_default_id.id
        bundle.unlink()
        self.assertFalse(self.env["ir.default"].browse(default_id).exists())

    def test_export_includes_ir_default(self):
        bundle = self._create_bundle(
            code="client_default_export",
            operations=[self._set_default_op("email", "export@example.com")],
        )
        bundle.action_apply()
        self._assert_applied(bundle)
        files = export_bundle_files(bundle)
        self.assertIn("data/ir_default.xml", files)
        xml = files["data/ir_default.xml"]
        self.assertIn('id="default_res_partner_email"', xml)
        self.assertIn('model="ir.default"', xml)
        self.assertIn("field_id", xml)
        self.assertIn("ref=", xml)
        self.assertIn("export@example.com", xml)
        manifest = files["__manifest__.py"]
        self.assertIn("data/ir_default.xml", manifest)

    def test_export_many2one_uses_a_stable_ref(self):
        bundle = self._create_bundle(
            code="client_default_export_m2o",
            operations=[
                self._set_default_op("company_id", value_xmlid="base.main_company")
            ],
        )
        bundle.action_apply()
        self._assert_applied(bundle)
        xml = export_bundle_files(bundle)["data/ir_default.xml"]
        self.assertIn("base.main_company", xml)
        self.assertIn("eval=", xml)

    def test_export_bundle_with_only_a_default(self):
        bundle = self._create_bundle(
            code="client_default_only",
            operations=[self._set_default_op("email", "only@example.com")],
        )
        bundle.action_apply()
        self._assert_applied(bundle)
        files = export_bundle_files(bundle)
        self.assertEqual(
            [name for name in files if name.startswith("data/")],
            ["data/ir_default.xml"],
        )

    def test_create_from_ui_sets_the_clicked_field(self):
        bundle = self._create_bundle(code="client_default_ui")
        self.env["customization.bundle"].create_from_ui(
            {
                "bundle_id": bundle.id,
                "action": "set_default",
                "model": "res.partner",
                "view_id": self.form_view.id,
                "view_type": "form",
                "anchor_kind": "field",
                "anchor_name": "email",
                "payload": {"value": "ui@example.com"},
                "apply": True,
            }
        )
        operation = bundle.operation_ids
        self.assertEqual(operation.type, "set_default")
        self.assertEqual(operation.payload.get("field_name"), "email")
        self.assertEqual(operation.state, "applied")
        self.assertEqual(
            json.loads(operation.generated_default_id.json_value), "ui@example.com"
        )

    def test_create_from_ui_refuses_a_page(self):
        bundle = self._create_bundle(code="client_default_page")
        view = self._form_with_page()
        with self.assertRaises(UserError):
            self.env["customization.bundle"].create_from_ui(
                {
                    "bundle_id": bundle.id,
                    "action": "set_default",
                    "model": "res.partner",
                    "view_id": view.id,
                    "view_type": "form",
                    "anchor_kind": "page",
                    "anchor_name": "extra_info",
                    "payload": {"value": "nope"},
                }
            )

    def test_payload_ui_keeps_an_empty_char_default(self):
        bundle = self._create_bundle(code="client_default_empty_ui")
        operation = self.env["customization.operation"].create(
            {
                "bundle_id": bundle.id,
                "type": "set_default",
                "model_id": self.partner_model.id,
                "payload_field_name": "email",
                "payload_value": "",
            }
        )
        self.assertEqual(operation.payload.get("field_name"), "email")
        self.assertEqual(operation.payload.get("value"), "")
        operation.action_apply()
        self.assertEqual(operation.state, "applied")
        self.assertEqual(json.loads(operation.generated_default_id.json_value), "")
