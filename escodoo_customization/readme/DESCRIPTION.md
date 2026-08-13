Upgrade-safe UI customizations stored as a **ledger of intentions**, not as
fragile XPath blobs in the database.

Each *bundle* groups operations for a client or project. Each *operation*
declares an intent (`add_field`, `place_field`, hide a field, set a modifier)
anchored on a **semantic target** (for example “after field `partner_id`” on a
named view). A compiler turns those operations into regular `ir.model.fields`
(`x_esc_*`) and inherited views.

On upgrade, a health check re-resolves anchors. Missing anchors are marked
`broken` with a reason; other operations are left intact. Customizations never
disappear silently.

This module is **not** a clone of Odoo Studio. Approvals stay in
`base_tier_validation`. Automations stay in `base.automation` /
`automation_oca`.
