# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from lxml import etree

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

DOCUMENT_KEY = "web_customizer_report.report_tester_document"
WRAPPER_KEY = "web_customizer_report.report_tester"
# Mirrors the shape every core document template has: a named block, a
# named table whose header and line cells are named, a t-field on the
# printed record and another inside the line loop.
DOCUMENT_ARCH = f"""
<t t-name="{DOCUMENT_KEY}">
    <div class="page">
        <div name="header_block">
            <span name="doc_title">Document</span>
            <span name="doc_reference" t-field="o.ref"/>
        </div>
        <table name="line_table">
            <thead>
                <tr>
                    <th name="th_name">Description</th>
                    <th name="th_quantity">Quantity</th>
                </tr>
            </thead>
            <tbody>
                <tr t-foreach="o.child_ids" t-as="line">
                    <td name="td_name"><span t-field="line.name"/></td>
                    <td name="td_email"><span t-field="line.email"/></td>
                </tr>
            </tbody>
        </table>
        <p name="note"><span t-field="o.comment"/></p>
        <p name="footnote"><span>Thank you</span></p>
    </div>
</t>
"""
WRAPPER_ARCH = f"""
<t t-name="{WRAPPER_KEY}">
    <t t-call="web.html_container">
        <t t-foreach="docs" t-as="o">
            <t t-call="{DOCUMENT_KEY}"/>
        </t>
    </t>
</t>
"""


@tagged("post_install", "-at_install")
class ReportCustomizationCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.document = cls.env["ir.ui.view"].create(
            {
                "name": "customization.tester.report.document",
                "type": "qweb",
                "key": DOCUMENT_KEY,
                "arch": DOCUMENT_ARCH,
            }
        )
        cls.wrapper = cls.env["ir.ui.view"].create(
            {
                "name": "customization.tester.report",
                "type": "qweb",
                "key": WRAPPER_KEY,
                "arch": WRAPPER_ARCH,
            }
        )
        cls.report = cls.env["ir.actions.report"].create(
            {
                "name": "Customization Tester",
                "model": "res.partner",
                "report_type": "qweb-pdf",
                "report_name": WRAPPER_KEY,
            }
        )
        cls.partner_model = cls.env["ir.model"]._get("res.partner")

    def _create_bundle(self, code="client_report_test"):
        return self.env["customization.bundle"].create(
            {"name": "Report test bundle", "code": code}
        )

    def _operation(self, bundle, **overrides):
        """Create a report operation on the tester document template."""
        vals = {
            "bundle_id": bundle.id,
            "type": "hide_field",
            "view_id": self.document.id,
            "view_type": "qweb",
            "anchor_kind": "field",
        }
        vals.update(overrides)
        return self.env["customization.operation"].create(vals)

    def _combined(self, view=None):
        """Return the combined arch of the template, inherits included."""
        view = view or self.document
        return view.with_context(lang=None)._get_combined_arch()

    def _node(self, name, view=None):
        nodes = self._combined(view).xpath(f"//*[@name='{name}']")
        return nodes[0] if nodes else None

    def _generated_arch(self, operation):
        arch = operation.generated_view_id.arch
        if isinstance(arch, bytes):
            arch = arch.decode()
        return etree.fromstring(arch.encode())

    def _core_template(self, xmlid):
        """Return a core document template, or skip when its addon is out."""
        view = self.env.ref(xmlid, raise_if_not_found=False)
        if not view:
            self.skipTest(f"{xmlid} is not installed in this database")
        return view
