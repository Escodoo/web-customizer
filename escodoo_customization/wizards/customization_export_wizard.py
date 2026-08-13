# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import base64

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
    data = fields.Binary(readonly=True)
    filename = fields.Char(readonly=True)

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        bundle_id = self.env.context.get("default_bundle_id")
        if bundle_id:
            bundle = self.env["customization.bundle"].browse(bundle_id)
            zip_bytes, filename = export_bundle_zip(bundle)
            values["bundle_id"] = bundle.id
            values["data"] = base64.b64encode(zip_bytes)
            values["filename"] = filename
        return values
