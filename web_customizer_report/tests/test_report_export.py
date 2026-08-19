# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import io
import zipfile

from odoo.tests import tagged

from odoo.addons.web_customizer.models.exporter import (
    export_bundle_files,
    export_bundle_zip,
)

from .common import ReportCustomizationCase


@tagged("post_install", "-at_install")
class TestReportExport(ReportCustomizationCase):
    def _publish_document(self):
        """Give the tester template an XML ID, as a real addon would."""
        self.env["ir.model.data"].create(
            {
                "module": "web_customizer_report",
                "name": "tester_document_view",
                "model": "ir.ui.view",
                "res_id": self.document.id,
            }
        )

    def test_exported_report_inherit_is_a_qweb_extension(self):
        self._publish_document()
        bundle = self._create_bundle()
        operation = self._operation(bundle, anchor_name="td_email")
        operation.action_apply()

        files = export_bundle_files(bundle)
        views = files["views/inherited_views.xml"]
        self.assertIn('<field name="type">qweb</field>', views)
        self.assertIn(
            f'<field name="key">{bundle.code}.view_operation_{operation.id}</field>',
            views,
        )
        self.assertIn(
            '<field name="inherit_id" ref="web_customizer_report.'
            'tester_document_view"/>',
            views,
        )
        self.assertIn('<field name="mode">extension</field>', views)
        # A template carries no model; claiming one would be a lie the
        # installed addon has to live with.
        self.assertNotIn('<field name="model">', views)
        self.assertIn("t-if", views)

    def test_exported_zip_carries_the_report_inherit(self):
        self._publish_document()
        bundle = self._create_bundle()
        self._operation(bundle, anchor_name="td_email").action_apply()

        content, filename = export_bundle_zip(bundle)
        self.assertEqual(filename, f"{bundle.code}.zip")
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = archive.namelist()
            self.assertIn(f"{bundle.code}/__manifest__.py", names)
            self.assertIn(f"{bundle.code}/views/inherited_views.xml", names)
            manifest = archive.read(f"{bundle.code}/__manifest__.py").decode()
        self.assertIn("'views/inherited_views.xml'", manifest)

    def test_exporting_the_invoice_depends_on_account_only(self):
        document = self._core_template("account.report_invoice_document")
        bundle = self._create_bundle()
        self._operation(
            bundle, view_id=document.id, anchor_name="td_quantity"
        ).action_apply()

        files = export_bundle_files(bundle)
        manifest = files["__manifest__.py"]
        self.assertIn("'account'", manifest)
        # The exported addon is what goes to git; it must run without the
        # authoring tool installed.
        self.assertNotIn("web_customizer", manifest)
        self.assertIn(
            '<field name="inherit_id" ref="account.report_invoice_document"/>',
            files["views/inherited_views.xml"],
        )
