# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.web_customizer.models.compiler import bind_generated_xmlids

from .report_compiler import (
    REPORT_ANCHOR_KINDS,
    REPORT_OPERATION_TYPES,
    REPORT_VIEW_TYPE,
    compile_report_operation,
    health_check_report_operation,
    is_report_operation,
)


class CustomizationOperation(models.Model):
    _inherit = "customization.operation"

    view_type = fields.Selection(
        selection_add=[(REPORT_VIEW_TYPE, "Report (QWeb)")],
        ondelete={REPORT_VIEW_TYPE: "cascade"},
    )
    anchor_kind = fields.Selection(
        selection_add=[("t_field", "Report Value")],
        ondelete={"t_field": "cascade"},
    )

    @api.constrains("view_type", "type", "anchor_kind", "view_id")
    def _check_report_operation(self):
        """Refuse a report operation the compiler could never honour.

        Failing on write keeps the ledger readable: an operation that can
        never compile is not worth storing as broken.
        """
        for rec in self:
            if not is_report_operation(rec):
                continue
            if rec.type not in REPORT_OPERATION_TYPES:
                raise ValidationError(
                    self.env._(
                        "A report template only accepts hide, rename, place "
                        "and move, not '%s'."
                    )
                    % rec.type
                )
            if (rec.anchor_kind or "field") not in REPORT_ANCHOR_KINDS:
                raise ValidationError(
                    self.env._(
                        "A report node is anchored on its name or on its "
                        "t-field, not on a %s."
                    )
                    % rec.anchor_kind
                )
            if rec.view_id and rec.view_id.type != REPORT_VIEW_TYPE:
                raise ValidationError(
                    self.env._("View '%s' is not a QWeb template.")
                    % rec.view_id.display_name
                )

    def _compile(self):
        self.ensure_one()
        if not is_report_operation(self):
            return super()._compile()
        compile_report_operation(self)
        bind_generated_xmlids(self)
        return True

    def _resolve_health(self):
        self.ensure_one()
        if not is_report_operation(self):
            return super()._resolve_health()
        return health_check_report_operation(self)
