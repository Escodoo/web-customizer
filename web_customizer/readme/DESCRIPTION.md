An open source, upgrade-safe alternative to Odoo Studio: customize the
backend UI by clicking, then ship the result as a real addon in git.

Customizations are stored as a **ledger of intentions**, not as fragile
XPath blobs in the database.

Each *bundle* groups operations for a client or project. Each *operation*
declares an intent (`add_field`, `place_field`, hide a field, set a modifier)
anchored on a **semantic target** (for example “after field `partner_id`” on a
named view). A compiler turns those operations into regular `ir.model.fields`
(`x_cust_*`) and inherited views. Applied bundles can be **exported** as a
plain Odoo addon to version in git.

Customization managers can turn on customization mode from the systray and
click a field, page tab, group title, or named button on a form, a list column
header, a kanban card field or button, a kanban header button or
progressbar, or a search field to add a field, place an
existing field, move a field the view already declares, add a notebook page
or group, hide it, change its label, set a
widget, restrict it to groups, or set modifiers. Click a navbar menu to hide
it, rename it, restrict it to groups, add a sibling or submenu (bound to a
window action with an XML ID), or move it after another menu or as a
submenu. Duplicate names (for example two `email`
fields) are chosen in the dialog. That writes the same operations as
the backend form.

On module update (`-u`), a health check re-resolves anchors automatically.
Missing anchors are marked `broken` with a reason; other operations are left
intact. Customizations never disappear silently. Compiled artifacts own XML
IDs under the bundle code, so uninstalling this module does not delete
unexported fields, views or menus. Git still needs the exported addon.
A hide, rename, groups or move write on a standard menu is exclusive
per type: a second bundle cannot overwrite the same snapshot.
The same rule applies to hide, label, widget, groups and modifier
operations on a view node: two live inherits of the same type on the
same anchor are refused. Two operations positioning the same field on one
view are also refused. Company on a bundle is only a filter tag; compiled
records stay global.

Moving a field relocates the node the view already declares instead of
adding a second copy, so it arrives with the widget, label and modifiers
the base view gave it, and it returns to its original spot once the
operation is dropped. A source that is missing, or that the view declares
more than once, is reported as broken rather than compiled into an
inherit the renderer would choke on.

What sets this apart from Odoo Studio is the storage model. Studio mutates
the database and keeps the result, so when a core view moves on upgrade the
only recovery path is to discard the customizations on that view. Here the
intent outlives the artifact: a moved anchor is re-resolved and only a
genuinely missing one is reported.

On a search view, filters and groupings are anchors of their own: click one
to hide or relabel it, or add a filter next to it. A new filter either
narrows records with a domain or groups them by a field. The domain is
checked before it is written, so a typo becomes a broken operation with a
reason instead of a search view nobody can open.

Pivot and graph views compile too. A pivot measure is clickable like any
other anchor; graph has no per-field DOM to click, since it draws on a
canvas, so graph operations are written from the backend form and compile
and export the same way.

Scope stops at the user interface, and not at all of it. Calendar and
gantt views, creating a model, and report editing are not covered; see
the roadmap. Approvals stay in `base_tier_validation`. Automations stay
in `base.automation` / `automation_oca`.
