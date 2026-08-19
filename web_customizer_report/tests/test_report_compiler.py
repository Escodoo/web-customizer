# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import ReportCustomizationCase


@tagged("post_install", "-at_install")
class TestReportCompiler(ReportCustomizationCase):
    def test_hide_named_node(self):
        bundle = self._create_bundle()
        operation = self._operation(bundle, anchor_name="td_email")
        operation.action_apply()
        self.assertEqual(operation.state, "applied", operation.broken_reason)
        view = operation.generated_view_id
        self.assertEqual(view.type, "qweb")
        self.assertFalse(view.model)
        self.assertEqual(view.key, f"{bundle.code}.view_operation_{operation.id}")
        self.assertEqual(view.inherit_id, self.document)
        self.assertEqual(self._node("td_email").get("t-if"), "False")

    def test_hide_keeps_the_other_nodes(self):
        bundle = self._create_bundle()
        self._operation(bundle, anchor_name="td_email").action_apply()
        self.assertIsNone(self._node("td_name").get("t-if"))

    def test_hide_anchored_on_a_printed_value(self):
        bundle = self._create_bundle()
        operation = self._operation(
            bundle, anchor_kind="t_field", anchor_name="o.comment"
        )
        operation.action_apply()
        self.assertEqual(operation.state, "applied", operation.broken_reason)
        nodes = self._combined().xpath("//*[@t-field='o.comment']")
        self.assertEqual(nodes[0].get("t-if"), "False")

    def test_generated_xmlid_belongs_to_the_bundle(self):
        bundle = self._create_bundle()
        operation = self._operation(bundle, anchor_name="td_email")
        operation.action_apply()
        xmlid = operation.generated_view_id.get_external_id()[
            operation.generated_view_id.id
        ]
        self.assertEqual(xmlid, f"{bundle.code}.view_operation_{operation.id}")

    def test_rename_a_static_label(self):
        bundle = self._create_bundle()
        operation = self._operation(
            bundle,
            type="set_string",
            anchor_name="th_quantity",
            payload={"string": "Qty"},
        )
        operation.action_apply()
        self.assertEqual(operation.state, "applied", operation.broken_reason)
        self.assertEqual(self._node("th_quantity").get("t-out"), "'Qty'")

    def test_rename_escapes_a_quote(self):
        bundle = self._create_bundle()
        operation = self._operation(
            bundle,
            type="set_string",
            anchor_name="th_name",
            payload={"string": "Client's item"},
        )
        operation.action_apply()
        self.assertEqual(operation.state, "applied", operation.broken_reason)
        self.assertEqual(self._node("th_name").get("t-out"), '"Client\'s item"')

    def test_rename_a_printed_value_is_broken(self):
        bundle = self._create_bundle()
        operation = self._operation(
            bundle,
            type="set_string",
            anchor_name="doc_reference",
            payload={"string": "Reference"},
        )
        operation.action_apply()
        self.assertEqual(operation.state, "broken")
        self.assertIn("record value", operation.broken_reason)

    def test_rename_without_a_label_is_broken(self):
        bundle = self._create_bundle()
        operation = self._operation(
            bundle, type="set_string", anchor_name="th_quantity", payload={}
        )
        operation.action_apply()
        self.assertEqual(operation.state, "broken")

    def test_place_a_value_next_to_a_cell(self):
        bundle = self._create_bundle()
        operation = self._operation(
            bundle,
            type="place_field",
            anchor_name="td_name",
            position="after",
            payload={"field_name": "line.function"},
        )
        operation.action_apply()
        self.assertEqual(operation.state, "applied", operation.broken_reason)
        placed = self._combined().xpath("//*[@t-field='line.function']")
        self.assertEqual(len(placed), 1)
        # A cell only makes sense next to a cell, so the row keeps its shape.
        self.assertEqual(placed[0].getparent().tag, "td")
        self.assertEqual(placed[0].getparent().getprevious().get("name"), "td_name")

    def test_place_a_value_next_to_a_block(self):
        bundle = self._create_bundle()
        operation = self._operation(
            bundle,
            type="place_field",
            anchor_name="header_block",
            position="after",
            payload={"field_name": "o.vat"},
        )
        operation.action_apply()
        self.assertEqual(operation.state, "applied", operation.broken_reason)
        placed = self._combined().xpath("//*[@t-field='o.vat']")
        self.assertEqual(len(placed), 1)
        self.assertEqual(placed[0].tag, "span")

    def test_place_inside_a_named_node(self):
        bundle = self._create_bundle()
        operation = self._operation(
            bundle,
            type="place_field",
            anchor_name="footnote",
            position="inside",
            payload={"field_name": "o.website"},
        )
        operation.action_apply()
        self.assertEqual(operation.state, "applied", operation.broken_reason)
        self.assertEqual(self._node("footnote")[-1].get("t-field"), "o.website")

    def test_place_an_unknown_field_is_broken(self):
        bundle = self._create_bundle()
        operation = self._operation(
            bundle,
            type="place_field",
            anchor_name="header_block",
            payload={"field_name": "o.x_not_a_field"},
        )
        operation.action_apply()
        self.assertEqual(operation.state, "broken")
        self.assertIn("x_not_a_field", operation.broken_reason)

    def test_place_through_a_non_relational_field_is_broken(self):
        bundle = self._create_bundle()
        operation = self._operation(
            bundle,
            type="place_field",
            anchor_name="header_block",
            payload={"field_name": "o.name.email"},
        )
        operation.action_apply()
        self.assertEqual(operation.state, "broken")
        self.assertIn("not relational", operation.broken_reason)

    def test_place_reads_through_a_relation(self):
        bundle = self._create_bundle()
        operation = self._operation(
            bundle,
            type="place_field",
            anchor_name="header_block",
            payload={"field_name": "o.company_id.name"},
        )
        operation.action_apply()
        self.assertEqual(operation.state, "applied", operation.broken_reason)

    def test_place_an_unknown_variable_is_broken(self):
        bundle = self._create_bundle()
        operation = self._operation(
            bundle,
            type="place_field",
            anchor_name="header_block",
            payload={"field_name": "invoice.name"},
        )
        operation.action_apply()
        self.assertEqual(operation.state, "broken")
        self.assertIn("invoice", operation.broken_reason)

    def test_place_a_bare_field_name_is_broken(self):
        bundle = self._create_bundle()
        operation = self._operation(
            bundle,
            type="place_field",
            anchor_name="header_block",
            payload={"field_name": "vat"},
        )
        operation.action_apply()
        self.assertEqual(operation.state, "broken")
        self.assertIn("report expression", operation.broken_reason)

    def test_move_a_named_node(self):
        bundle = self._create_bundle()
        operation = self._operation(
            bundle,
            type="move_field",
            anchor_name="header_block",
            position="before",
            payload={"field_name": "note"},
        )
        operation.action_apply()
        self.assertEqual(operation.state, "applied", operation.broken_reason)
        self.assertEqual(self._node("header_block").getprevious().get("name"), "note")
        self.assertEqual(len(self._combined().xpath("//*[@name='note']")), 1)

    def test_move_a_missing_node_is_broken(self):
        bundle = self._create_bundle()
        operation = self._operation(
            bundle,
            type="move_field",
            anchor_name="header_block",
            payload={"field_name": "nowhere"},
        )
        operation.action_apply()
        self.assertEqual(operation.state, "broken")
        self.assertIn("nothing to move", operation.broken_reason)

    def test_move_onto_itself_is_broken(self):
        bundle = self._create_bundle()
        operation = self._operation(
            bundle,
            type="move_field",
            anchor_name="note",
            payload={"field_name": "note"},
        )
        operation.action_apply()
        self.assertEqual(operation.state, "broken")
        self.assertIn("next to itself", operation.broken_reason)

    def test_an_ambiguous_anchor_is_broken(self):
        self.env["ir.ui.view"].create(
            {
                "name": "customization.tester.report.document.twin",
                "type": "qweb",
                "key": "web_customizer_report.tester_twin",
                "inherit_id": self.document.id,
                "mode": "extension",
                "arch": """
                    <xpath expr="//*[@name='footnote']" position="after">
                        <p name="note"><span>Second note</span></p>
                    </xpath>
                """,
            }
        )
        bundle = self._create_bundle()
        operation = self._operation(bundle, anchor_name="note")
        operation.action_apply()
        self.assertEqual(operation.state, "broken")
        self.assertIn("occurrence", operation.broken_reason)

        operation.anchor_occurrence = 2
        operation.action_apply()
        self.assertEqual(operation.state, "applied", operation.broken_reason)
        notes = self._combined().xpath("//*[@name='note']")
        self.assertIsNone(notes[0].get("t-if"))
        self.assertEqual(notes[1].get("t-if"), "False")

    def test_a_missing_anchor_is_broken(self):
        bundle = self._create_bundle()
        operation = self._operation(bundle, anchor_name="not_in_the_template")
        operation.action_apply()
        self.assertEqual(operation.state, "broken")
        self.assertIn("not_in_the_template", operation.broken_reason)

    def test_the_wrapper_template_is_refused(self):
        bundle = self._create_bundle()
        operation = self._operation(
            bundle, view_id=self.wrapper.id, anchor_name="header_block"
        )
        operation.action_apply()
        self.assertEqual(operation.state, "broken")
        self.assertIn("report_tester_document", operation.broken_reason)

    def test_health_check_follows_the_anchor(self):
        bundle = self._create_bundle()
        operation = self._operation(bundle, anchor_name="td_email")
        operation.action_apply()
        self.assertEqual(operation.state, "applied")

        # An upstream template that stops naming the node is what a module
        # upgrade looks like from here.
        operation.anchor_name = "td_email_renamed_upstream"
        bundle.action_health_check()
        self.assertEqual(operation.state, "broken")
        self.assertIn("td_email_renamed_upstream", operation.broken_reason)
        self.assertFalse(operation.generated_view_id.active)
        self.assertIsNone(self._node("td_email").get("t-if"))

        operation.anchor_name = "td_email"
        bundle.action_health_check()
        self.assertEqual(operation.state, "applied", operation.broken_reason)
        self.assertFalse(operation.broken_reason)
        self.assertTrue(operation.generated_view_id.active)
        self.assertEqual(self._node("td_email").get("t-if"), "False")

    def test_an_unsupported_type_is_refused(self):
        bundle = self._create_bundle()
        with self.assertRaises(ValidationError):
            self._operation(
                bundle,
                type="set_widget",
                anchor_name="td_email",
                payload={"widget": "badge"},
            )

    def test_an_unsupported_anchor_kind_is_refused(self):
        bundle = self._create_bundle()
        with self.assertRaises(ValidationError):
            self._operation(bundle, anchor_kind="page", anchor_name="td_email")

    def test_a_non_qweb_view_is_refused(self):
        form = self.env["ir.ui.view"].create(
            {
                "name": "customization.tester.partner.form",
                "model": "res.partner",
                "type": "form",
                "arch": "<form><field name='name'/></form>",
            }
        )
        bundle = self._create_bundle()
        with self.assertRaises(ValidationError):
            self._operation(bundle, view_id=form.id, anchor_name="name")

    def test_two_hides_on_the_same_anchor_are_refused(self):
        first = self._create_bundle("client_report_one")
        self._operation(first, anchor_name="td_email").action_apply()
        second = self._create_bundle("client_report_two")
        with self.assertRaises(ValidationError):
            self._operation(second, anchor_name="td_email")

    def test_two_placements_of_the_same_value_are_refused(self):
        bundle = self._create_bundle()
        self._operation(
            bundle,
            type="place_field",
            anchor_name="header_block",
            payload={"field_name": "o.vat"},
        ).action_apply()
        with self.assertRaises(ValidationError):
            self._operation(
                bundle,
                type="place_field",
                anchor_name="footnote",
                payload={"field_name": "o.vat"},
            )

    def test_dropping_the_operation_restores_the_template(self):
        bundle = self._create_bundle()
        operation = self._operation(bundle, anchor_name="td_email")
        operation.action_apply()
        operation.unlink()
        self.assertIsNone(self._node("td_email").get("t-if"))


@tagged("post_install", "-at_install")
class TestReportCompilerOnCoreTemplates(ReportCustomizationCase):
    def test_hide_a_column_of_the_invoice(self):
        document = self._core_template("account.report_invoice_document")
        bundle = self._create_bundle()
        header = self._operation(bundle, view_id=document.id, anchor_name="th_quantity")
        cell = self._operation(bundle, view_id=document.id, anchor_name="td_quantity")
        (header | cell).action_apply()
        self.assertEqual(header.state, "applied", header.broken_reason)
        self.assertEqual(cell.state, "applied", cell.broken_reason)
        self.assertEqual(self._node("th_quantity", document).get("t-if"), "False")
        self.assertEqual(self._node("td_quantity", document).get("t-if"), "False")

    def test_place_a_value_after_the_invoice_date(self):
        document = self._core_template("account.report_invoice_document")
        bundle = self._create_bundle()
        operation = self._operation(
            bundle,
            view_id=document.id,
            type="place_field",
            anchor_name="invoice_date",
            payload={"field_name": "o.invoice_origin"},
        )
        operation.action_apply()
        self.assertEqual(operation.state, "applied", operation.broken_reason)
        placed = self._combined(document).xpath("//*[@t-field='o.invoice_origin']")
        self.assertTrue(placed)

    def test_a_field_the_invoice_model_lacks_is_broken(self):
        document = self._core_template("account.report_invoice_document")
        bundle = self._create_bundle()
        operation = self._operation(
            bundle,
            view_id=document.id,
            type="place_field",
            anchor_name="invoice_date",
            payload={"field_name": "o.order_line"},
        )
        operation.action_apply()
        self.assertEqual(operation.state, "broken")
        self.assertIn("account.move", operation.broken_reason)

    def test_the_invoice_wrapper_is_refused(self):
        wrapper = self._core_template("account.report_invoice")
        bundle = self._create_bundle()
        operation = self._operation(
            bundle, view_id=wrapper.id, anchor_name="invoice_date"
        )
        operation.action_apply()
        self.assertEqual(operation.state, "broken")
        self.assertIn("account.report_invoice_document", operation.broken_reason)

    def test_rename_a_column_of_the_sale_order(self):
        document = self._core_template("sale.report_saleorder_document")
        bundle = self._create_bundle()
        operation = self._operation(
            bundle,
            view_id=document.id,
            type="set_string",
            anchor_name="th_quantity",
            payload={"string": "Qty"},
        )
        operation.action_apply()
        self.assertEqual(operation.state, "applied", operation.broken_reason)
        self.assertEqual(self._node("th_quantity", document).get("t-out"), "'Qty'")
