# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from lxml import etree

from odoo import Command
from odoo.tests import tagged

from .common import CustomizationCase


@tagged("post_install", "-at_install")
class TestCustomizationSearchFilter(CustomizationCase):
    """A filter narrows records with a domain or groups them by a field."""

    def _add_filter(self, payload, anchor="email", anchor_kind="field", view=None):
        return Command.create(
            {
                "type": "add_filter",
                "model_id": self.partner_model.id,
                "view_id": (view or self.search_view).id,
                "view_type": "search",
                "anchor_kind": anchor_kind,
                "anchor_name": anchor,
                "position": "after",
                "payload": payload,
            }
        )

    def _filter_node(self, view, name):
        tree = etree.fromstring(view.get_combined_arch())
        nodes = tree.xpath(f"//filter[@name='{name}']")
        self.assertEqual(len(nodes), 1, f"expected one filter named {name}")
        return nodes[0]

    def test_add_filter_with_domain(self):
        bundle = self._create_bundle(
            code="client_filter_domain",
            operations=[
                self._add_filter(
                    {
                        "string": "Companies Only",
                        "name": "x_cust_companies_only",
                        "domain": "[('is_company', '=', True)]",
                    }
                )
            ],
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        node = self._filter_node(self.search_view, "x_cust_companies_only")
        self.assertEqual(node.get("string"), "Companies Only")
        self.assertEqual(node.get("domain"), "[('is_company', '=', True)]")

    def test_add_group_by_filter(self):
        bundle = self._create_bundle(
            code="client_filter_groupby",
            operations=[
                self._add_filter(
                    {
                        "string": "By Country",
                        "name": "x_cust_by_country",
                        "group_by": "country_id",
                    }
                )
            ],
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        node = self._filter_node(self.search_view, "x_cust_by_country")
        self.assertEqual(node.get("context"), "{'group_by': 'country_id'}")
        self.assertIsNone(node.get("domain"))

    def test_filter_name_is_derived_from_the_label(self):
        bundle = self._create_bundle(
            code="client_filter_autoname",
            operations=[
                self._add_filter(
                    {"string": "Active Ones", "domain": "[('active', '=', True)]"}
                )
            ],
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        self.assertEqual(bundle.operation_ids.payload.get("name"), "x_cust_active_ones")

    def test_syntactically_broken_domain_is_refused(self):
        bundle = self._create_bundle(
            code="client_filter_syntax",
            operations=[
                self._add_filter(
                    {"string": "Broken", "domain": "[('active', '=' True)]"}
                )
            ],
        )
        bundle.action_apply()
        operation = bundle.operation_ids
        self.assertEqual(operation.state, "broken")
        self.assertIn("Python", operation.broken_reason)
        self.assertFalse(operation.generated_view_id)

    def test_malformed_literal_domain_is_refused(self):
        """A well-formed list can still be a domain no operator accepts."""
        bundle = self._create_bundle(
            code="client_filter_shape",
            operations=[self._add_filter({"string": "Shape", "domain": "['&']"})],
        )
        bundle.action_apply()
        operation = bundle.operation_ids
        self.assertEqual(operation.state, "broken")
        self.assertIn("malformed", operation.broken_reason)

    def test_dynamic_domain_is_accepted(self):
        """context_today cannot be evaluated here, so it only gets a syntax check."""
        domain = "[('write_date', '>=', context_today().strftime('%Y-%m-%d'))]"
        bundle = self._create_bundle(
            code="client_filter_dynamic",
            operations=[
                self._add_filter(
                    {
                        "string": "Touched Today",
                        "name": "x_cust_touched",
                        "domain": domain,
                    }
                )
            ],
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        self.assertEqual(
            self._filter_node(self.search_view, "x_cust_touched").get("domain"), domain
        )

    def test_group_by_unknown_field_is_refused(self):
        bundle = self._create_bundle(
            code="client_filter_unknown",
            operations=[
                self._add_filter({"string": "Nope", "group_by": "x_does_not_exist"})
            ],
        )
        bundle.action_apply()
        operation = bundle.operation_ids
        self.assertEqual(operation.state, "broken")
        self.assertIn("does not exist", operation.broken_reason)

    def test_group_by_non_groupable_field_is_refused(self):
        bundle = self._create_bundle(
            code="client_filter_ungroupable",
            operations=[
                self._add_filter({"string": "By Children", "group_by": "child_ids"})
            ],
        )
        bundle.action_apply()
        operation = bundle.operation_ids
        self.assertEqual(operation.state, "broken")
        self.assertIn("grouped", operation.broken_reason)

    def test_domain_and_group_by_together_are_refused(self):
        bundle = self._create_bundle(
            code="client_filter_both",
            operations=[
                self._add_filter(
                    {
                        "string": "Both",
                        "domain": "[('active', '=', True)]",
                        "group_by": "country_id",
                    }
                )
            ],
        )
        bundle.action_apply()
        operation = bundle.operation_ids
        self.assertEqual(operation.state, "broken")
        self.assertIn("either", operation.broken_reason)

    def test_filter_outside_a_search_view_is_refused(self):
        bundle = self._create_bundle(
            code="client_filter_form",
            operations=[
                Command.create(
                    {
                        "type": "add_filter",
                        "model_id": self.partner_model.id,
                        "view_id": self.form_view.id,
                        "view_type": "form",
                        "anchor_name": "email",
                        "position": "after",
                        "payload": {
                            "string": "Nope",
                            "domain": "[('active', '=', True)]",
                        },
                    }
                )
            ],
        )
        bundle.action_apply()
        operation = bundle.operation_ids
        self.assertEqual(operation.state, "broken")
        self.assertIn("search", operation.broken_reason)

    def test_anchor_on_an_existing_filter(self):
        view = self.env["ir.ui.view"].create(
            {
                "name": "customization.tester.partner.search.filters",
                "model": "res.partner",
                "type": "search",
                "arch": """
                    <search>
                        <field name="name"/>
                        <filter name="inactive" string="Archived"
                            domain="[('active', '=', False)]"/>
                    </search>
                """,
            }
        )
        bundle = self._create_bundle(
            code="client_filter_anchor",
            operations=[
                self._add_filter(
                    {
                        "string": "Companies",
                        "name": "x_cust_companies",
                        "domain": "[('is_company', '=', True)]",
                    },
                    anchor="inactive",
                    anchor_kind="filter",
                    view=view,
                )
            ],
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        self.assertTrue(self._filter_node(view, "x_cust_companies") is not None)

    def test_hide_an_existing_filter(self):
        view = self.env["ir.ui.view"].create(
            {
                "name": "customization.tester.partner.search.hide",
                "model": "res.partner",
                "type": "search",
                "arch": """
                    <search>
                        <field name="name"/>
                        <filter name="inactive" string="Archived"
                            domain="[('active', '=', False)]"/>
                    </search>
                """,
            }
        )
        bundle = self._create_bundle(
            code="client_filter_hide",
            operations=[
                Command.create(
                    {
                        "type": "hide_field",
                        "model_id": self.partner_model.id,
                        "view_id": view.id,
                        "view_type": "search",
                        "anchor_kind": "filter",
                        "anchor_name": "inactive",
                        "payload": {},
                    }
                )
            ],
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        self.assertEqual(self._filter_node(view, "inactive").get("invisible"), "True")

    def test_add_filter_from_the_ui(self):
        bundle = self._create_bundle(code="client_filter_ui")
        self.env["customization.bundle"].create_from_ui(
            {
                "bundle_id": bundle.id,
                "action": "add_filter",
                "model": "res.partner",
                "view_id": self.search_view.id,
                "view_type": "search",
                "anchor_name": "email",
                "anchor_kind": "field",
                "payload": {
                    "string": "Companies UI",
                    "domain": "[('is_company', '=', True)]",
                },
                "apply": True,
            }
        )
        operation = bundle.operation_ids
        self.assertEqual(operation.type, "add_filter")
        self.assertEqual(operation.state, "applied")
        self.assertIn("Companies UI", self.search_view.get_combined_arch())
