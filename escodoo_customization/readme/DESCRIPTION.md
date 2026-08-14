Upgrade-safe UI customizations stored as a **ledger of intentions**, not as
fragile XPath blobs in the database.

Each *bundle* groups operations for a client or project. Each *operation*
declares an intent (`add_field`, `place_field`, hide a field, set a modifier)
anchored on a **semantic target** (for example “after field `partner_id`” on a
named view). A compiler turns those operations into regular `ir.model.fields`
(`x_esc_*`) and inherited views. Applied bundles can be **exported** as a
plain Odoo addon to version in git.

Customization managers can turn on customization mode from the systray and
click a field, page tab, group title, or named button on a form, a list column
header, a kanban card field or button, a kanban header button or
progressbar, or a search field to add a field, place an
existing field, add a notebook page or group, hide it, change its label, set a
widget, restrict it to groups, or set modifiers. Click a navbar menu to hide
it, rename it, restrict it to groups, add a sibling or submenu (bound to a
window action with an XML ID), or move it after another menu or as a
submenu. Duplicate names (for example two `email`
fields) are chosen in the dialog. That writes the same ledger operations as
the backend form.

On module update (`-u`), a health check re-resolves anchors automatically.
Missing anchors are marked `broken` with a reason; other operations are left
intact. Customizations never disappear silently. Compiled artifacts own XML
IDs under the bundle code, so uninstalling this ledger does not delete
unexported fields, views or menus. Git still needs the exported addon.
A hide, rename, groups or move write on a standard menu is exclusive
per type: a second bundle cannot overwrite the same snapshot.
The same rule applies to hide, label, widget, groups and modifier
operations on a view node: two live inherits of the same type on the
same anchor are refused. Placing the same field twice on one view is
also refused. Company on a bundle is only a filter tag; compiled
records stay global.

This module is **not** a clone of Odoo Studio. Approvals stay in
`base_tier_validation`. Automations stay in `base.automation` /
`automation_oca`.
