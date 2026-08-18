# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import new_test_user

from odoo.addons.web_customizer.hooks import health_check_on_upgrade

from .common import CustomizationCase


@tagged("post_install", "-at_install")
class TestCustomizationSecurity(CustomizationCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cust_user = new_test_user(
            cls.env,
            login="esc_cust_user",
            groups="web_customizer.group_customization_user",
        )
        cls.settings_user = new_test_user(
            cls.env,
            login="esc_cust_settings",
            groups="base.group_system",
        )
        cls.manager_user = new_test_user(
            cls.env,
            login="esc_cust_manager",
            groups="web_customizer.group_customization_manager,base.group_system",
        )

    def _hide_email_bundle(self, code):
        return self._create_bundle(
            code=code,
            operations=[
                Command.create(
                    {
                        "type": "hide_field",
                        "model_id": self.partner_model.id,
                        "view_id": self.form_view.id,
                        "view_type": "form",
                        "anchor_name": "email",
                        "payload": {},
                    }
                )
            ],
        )

    def test_user_cannot_read_other_company_operations(self):
        company_b = self.env["res.company"].create({"name": "Other Co"})
        user_a = new_test_user(
            self.env,
            login="esc_cust_co_a",
            groups="web_customizer.group_customization_user",
            company_id=self.env.company.id,
            company_ids=[Command.set(self.env.company.ids)],
        )
        bundle_b = self.env["customization.bundle"].create(
            {
                "name": "Other company",
                "code": "client_other_co",
                "company_id": company_b.id,
                "operation_ids": [
                    Command.create(
                        {
                            "type": "hide_field",
                            "model_id": self.partner_model.id,
                            "view_id": self.form_view.id,
                            "view_type": "form",
                            "anchor_name": "email",
                            "payload": {},
                        }
                    )
                ],
            }
        )
        operation = bundle_b.operation_ids
        visible = (
            self.env["customization.operation"]
            .with_user(user_a)
            .search([("id", "=", operation.id)])
        )
        self.assertFalse(visible)

    def test_user_can_read_but_not_create(self):
        bundle = self._create_bundle(code="client_acl_read")
        self.assertEqual(
            bundle.with_user(self.cust_user).name,
            "Test bundle",
        )
        with self.assertRaises(AccessError):
            self.env["customization.bundle"].with_user(self.cust_user).create(
                {"name": "Nope", "code": "client_acl_create"}
            )

    def test_settings_user_cannot_apply_or_health_check(self):
        bundle = self._hide_email_bundle("client_acl_settings")
        with self.assertRaises(AccessError):
            bundle.with_user(self.settings_user).action_apply()
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        with self.assertRaises(AccessError):
            bundle.with_user(self.settings_user).action_health_check()
        with self.assertRaises(AccessError):
            bundle.with_user(self.settings_user).action_reapply()
        with self.assertRaises(AccessError):
            bundle.operation_ids.with_user(self.settings_user).action_apply()

    def test_settings_user_cannot_unlink(self):
        bundle = self._create_bundle(code="client_acl_unlink")
        with self.assertRaises(AccessError):
            bundle.with_user(self.settings_user).unlink()

    def test_manager_can_apply(self):
        bundle = self._hide_email_bundle("client_acl_manager")
        bundle.with_user(self.manager_user).action_apply()
        self.assertEqual(bundle.state, "applied")

    def test_health_check_on_upgrade_marks_missing_anchor(self):
        bundle = self._hide_email_bundle("client_acl_upgrade")
        bundle.action_apply()
        operation = bundle.operation_ids
        operation.anchor_name = "does_not_exist"
        health_check_on_upgrade(self.env)
        self.assertEqual(operation.state, "broken")
        self.assertTrue(operation.broken_reason)

    def test_register_hook_runs_health_check_after_module_update(self):
        bundle = self._hide_email_bundle("client_acl_hook")
        bundle.action_apply()
        operation = bundle.operation_ids
        operation.anchor_name = "does_not_exist"
        updated = list(self.env.registry.updated_modules)
        self.env.registry.updated_modules = updated + ["base"]
        try:
            self.env["customization.bundle"]._register_hook()
        finally:
            self.env.registry.updated_modules = updated
        self.assertEqual(operation.state, "broken")

    def test_register_hook_skips_health_check_without_module_update(self):
        bundle = self._hide_email_bundle("client_acl_nohook")
        bundle.action_apply()
        operation = bundle.operation_ids
        operation.anchor_name = "does_not_exist"
        updated = list(self.env.registry.updated_modules)
        self.env.registry.updated_modules = []
        try:
            self.env["customization.bundle"]._register_hook()
        finally:
            self.env.registry.updated_modules = updated
        self.assertEqual(operation.state, "applied")
