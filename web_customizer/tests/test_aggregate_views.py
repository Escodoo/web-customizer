# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from lxml import etree

from odoo import Command
from odoo.tests import tagged

from .common import CustomizationCase


@tagged("post_install", "-at_install")
class TestCustomizationAggregateViews(CustomizationCase):
    """Pivot and graph anchor on fields and read a narrow set of attributes."""

    def _place(self, view, view_type, anchor, field_name, payload_extra=None):
        payload = {"field_name": field_name}
        payload.update(payload_extra or {})
        return Command.create(
            {
                "type": "place_field",
                "model_id": self.partner_model.id,
                "view_id": view.id,
                "view_type": view_type,
                "anchor_name": anchor,
                "position": "after",
                "payload": payload,
            }
        )

    def _field_node(self, view, name):
        tree = etree.fromstring(view.get_combined_arch())
        nodes = tree.xpath(f"//field[@name='{name}']")
        self.assertEqual(len(nodes), 1, f"expected one {name} node")
        return nodes[0]

    def test_place_field_on_pivot_defaults_to_measure(self):
        bundle = self._create_bundle(
            code="client_pivot_measure",
            operations=[
                Command.create(
                    {
                        "type": "add_field",
                        "sequence": 10,
                        "model_id": self.partner_model.id,
                        "payload": {
                            "ttype": "integer",
                            "string": "Visit Count",
                            "name": "x_cust_visit_count",
                        },
                    }
                ),
                self._place(
                    self.pivot_view, "pivot", "color", "x_cust_visit_count"
                ),
            ],
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        node = self._field_node(self.pivot_view, "x_cust_visit_count")
        self.assertEqual(node.get("type"), "measure")

    def test_place_row_grouping_on_pivot(self):
        bundle = self._create_bundle(
            code="client_pivot_row",
            operations=[
                self._place(
                    self.pivot_view,
                    "pivot",
                    "company_type",
                    "country_id",
                    {"field_type": "row"},
                )
            ],
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        node = self._field_node(self.pivot_view, "country_id")
        self.assertEqual(node.get("type"), "row")

    def test_place_grouping_on_graph_omits_type(self):
        """A graph groupby is an attribute-less node; a type would make it a measure."""
        bundle = self._create_bundle(
            code="client_graph_groupby",
            operations=[
                self._place(
                    self.graph_view,
                    "graph",
                    "company_type",
                    "country_id",
                    {"field_type": "groupby"},
                )
            ],
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        node = self._field_node(self.graph_view, "country_id")
        self.assertIsNone(node.get("type"))

    def test_graph_field_type_groupby_is_refused_on_pivot(self):
        bundle = self._create_bundle(
            code="client_pivot_bad_type",
            operations=[
                self._place(
                    self.pivot_view,
                    "pivot",
                    "color",
                    "country_id",
                    {"field_type": "groupby"},
                )
            ],
        )
        bundle.action_apply()
        operation = bundle.operation_ids
        self.assertEqual(operation.state, "broken")
        self.assertIn("groupby", operation.broken_reason)

    def test_pivot_row_type_is_refused_on_graph(self):
        bundle = self._create_bundle(
            code="client_graph_bad_type",
            operations=[
                self._place(
                    self.graph_view,
                    "graph",
                    "company_type",
                    "country_id",
                    {"field_type": "row"},
                )
            ],
        )
        bundle.action_apply()
        operation = bundle.operation_ids
        self.assertEqual(operation.state, "broken")
        self.assertIn("row", operation.broken_reason)

    def test_hide_measure_uses_invisible_not_column_invisible(self):
        bundle = self._create_bundle(
            code="client_pivot_hide",
            operations=[
                Command.create(
                    {
                        "type": "hide_field",
                        "model_id": self.partner_model.id,
                        "view_id": self.pivot_view.id,
                        "view_type": "pivot",
                        "anchor_name": "color",
                        "payload": {},
                    }
                )
            ],
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        node = self._field_node(self.pivot_view, "color")
        self.assertEqual(node.get("invisible"), "True")
        self.assertIsNone(node.get("column_invisible"))

    def test_pivot_refuses_a_non_field_anchor(self):
        """A page anchor would compile into an inherit the pivot parser ignores."""
        bundle = self._create_bundle(
            code="client_pivot_page",
            operations=[
                Command.create(
                    {
                        "type": "set_string",
                        "model_id": self.partner_model.id,
                        "view_id": self.pivot_view.id,
                        "view_type": "pivot",
                        "anchor_kind": "page",
                        "anchor_name": "whatever",
                        "payload": {"string": "Nope"},
                    }
                )
            ],
        )
        bundle.action_apply()
        operation = bundle.operation_ids
        self.assertEqual(operation.state, "broken")
        self.assertIn("field", operation.broken_reason)

    def test_pivot_refuses_readonly_modifier(self):
        bundle = self._create_bundle(
            code="client_pivot_readonly",
            operations=[
                Command.create(
                    {
                        "type": "set_modifier",
                        "model_id": self.partner_model.id,
                        "view_id": self.pivot_view.id,
                        "view_type": "pivot",
                        "anchor_name": "color",
                        "payload": {"modifiers": {"readonly": "True"}},
                    }
                )
            ],
        )
        bundle.action_apply()
        operation = bundle.operation_ids
        self.assertEqual(operation.state, "broken")
        self.assertIn("readonly", operation.broken_reason)

    def test_set_string_on_graph_measure(self):
        bundle = self._create_bundle(
            code="client_graph_label",
            operations=[
                Command.create(
                    {
                        "type": "set_string",
                        "model_id": self.partner_model.id,
                        "view_id": self.graph_view.id,
                        "view_type": "graph",
                        "anchor_name": "color",
                        "payload": {"string": "Colour Index"},
                    }
                )
            ],
        )
        bundle.action_apply()
        self.assertEqual(bundle.state, "applied")
        node = self._field_node(self.graph_view, "color")
        self.assertEqual(node.get("string"), "Colour Index")
