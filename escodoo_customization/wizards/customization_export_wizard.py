# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import base64
from urllib.parse import quote

from odoo import api, fields, models

from ..models.exporter import export_bundle_zip


class CustomizationExportWizard(models.TransientModel):
    _name = "customization.export.wizard"
    _description = "Export Customization Bundle"

    bundle_id = fields.Many2one(
        "customization.bundle",
        required=True,
        ondelete="cascade",
    )
    data = fields.Binary(readonly=True, attachment=False)
    filename = fields.Char(readonly=True)

    @api.model
    def _create_from_bundle(self, bundle):
        zip_bytes, filename = export_bundle_zip(bundle)
        return self.create(
            {
                "bundle_id": bundle.id,
                "data": base64.b64encode(zip_bytes).decode(),
                "filename": filename,
            }
        )

    def action_download(self):
        """Return a browser download of the generated addon zip."""
        self.ensure_one()
        filename = self.filename or f"{self.bundle_id.code}.zip"
        return {
            "type": "ir.actions.act_url",
            "url": (
                f"/web/content/{self._name}/{self.id}/data/{quote(filename)}"
                "?download=true"
            ),
            "target": "self",
        }
