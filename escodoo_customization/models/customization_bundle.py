# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class CustomizationBundle(models.Model):
    _name = "customization.bundle"
    _description = "Customization Bundle"
    _order = "name"

    name = fields.Char(required=True)
    code = fields.Char(
        required=True,
        help="Technical slug used later as the exported addon name "
        "(for example client_acme).",
    )
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("applied", "Applied"),
            ("needs_reapply", "Needs Re-apply"),
        ],
        compute="_compute_state",
        store=True,
    )
    company_id = fields.Many2one("res.company", ondelete="set null")
    operation_ids = fields.One2many(
        "customization.operation",
        "bundle_id",
        string="Operations",
    )
    operation_count = fields.Integer(compute="_compute_broken_count")
    broken_count = fields.Integer(compute="_compute_broken_count")

    _sql_constraints = [  # noqa: RUF012
        ("code_unique", "UNIQUE(code)", "The bundle code must be unique."),
    ]

    @api.constrains("code")
    def _check_code(self):
        for rec in self:
            if not rec.code or not re.match(r"^[a-z][a-z0-9_]*$", rec.code):
                raise ValidationError(
                    self.env._(
                        "Bundle code must start with a letter and contain only "
                        "lowercase letters, digits and underscores."
                    )
                )

    @api.depends("operation_ids.state")
    def _compute_state(self):
        for rec in self:
            ops = rec.operation_ids.filtered(lambda o: o.state != "archived")
            if not ops or all(o.state == "draft" for o in ops):
                rec.state = "draft"
            elif any(o.state == "broken" for o in ops):
                rec.state = "needs_reapply"
            elif all(o.state == "applied" for o in ops):
                rec.state = "applied"
            else:
                rec.state = "needs_reapply"

    @api.depends("operation_ids.state")
    def _compute_broken_count(self):
        for rec in self:
            rec.operation_count = len(rec.operation_ids)
            rec.broken_count = len(
                rec.operation_ids.filtered(lambda o: o.state == "broken")
            )

    def action_apply(self):
        """Compile draft and broken operations, in sequence."""
        self.ensure_one()
        operations = self.operation_ids.filtered(
            lambda o: o.state in ("draft", "broken")
        ).sorted("sequence")
        for operation in operations:
            operation.action_apply()
        return True

    def action_reapply(self):
        """Recompile every non-archived operation."""
        self.ensure_one()
        operations = self.operation_ids.filtered(
            lambda o: o.state != "archived"
        ).sorted("sequence")
        for operation in operations:
            operation.action_apply()
        return True

    def action_health_check(self):
        """Re-resolve anchors without creating fields or views."""
        self.ensure_one()
        operations = self.operation_ids.filtered(
            lambda o: o.state not in ("archived", "draft")
        ).sorted("sequence")
        for operation in operations:
            operation.action_health_check()
        return True

    def action_export(self):
        """Download an installable addon generated from applied operations."""
        self.ensure_one()
        return {
            "name": self.env._("Export Addon"),
            "type": "ir.actions.act_window",
            "res_model": "customization.export.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_bundle_id": self.id},
        }

    def unlink(self):
        # Cascade at SQL level would skip operation.unlink() and leak generated
        # views/fields. Unlink operations through the ORM first.
        self.mapped("operation_ids").unlink()
        return super().unlink()
