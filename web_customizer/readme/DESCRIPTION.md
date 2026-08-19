An open source, upgrade-safe alternative to Odoo Studio: customize the
backend UI by clicking, then ship the result as a real addon in git.

Customizations are stored as a **ledger of intentions**, not as fragile
XPath blobs in the database.

Each *bundle* groups operations for a client or project. Each *operation*
declares an intent (`add_field`, `set_default`, `place_field`, hide a field,
set a modifier) anchored on a **semantic target** (for example “after field
`partner_id`” on a named view). A compiler turns those operations into
regular `ir.model.fields` (`x_cust_*`), inherited views and global
`ir.default` records. Applied bundles can be **exported** as a
plain Odoo addon to version in git.

Customization managers can turn on customization mode from the systray and
click a field, page tab, group title, or named button on a form, a list column
header, a kanban card field or button, a kanban header button or
progressbar, or a search field to add a field, place an
existing field, move a field the view already declares, add a notebook page
or group, hide it, change its label, set a
widget, restrict it to groups, set a global default value, or set modifiers.
Click a navbar menu to hide
it, rename it, restrict it to groups, add a sibling or submenu (bound to a
window action with an XML ID), or move it after another menu or as a
submenu. Duplicate names (for example two `email`
fields) are chosen in the dialog. That writes the same operations as
the backend form.

On module update (`-u`), a health check re-resolves anchors automatically.
Missing anchors are marked `broken` with a reason; other operations are left
intact. Customizations never disappear silently. Compiled artifacts own XML
IDs under the bundle code, so uninstalling this module does not delete
unexported fields, views, menus or defaults. Git still needs the exported addon.
A hide, rename, groups or move write on a standard menu is exclusive
per type: a second bundle cannot overwrite the same snapshot.
The same rule applies to hide, label, widget, groups and modifier
operations on a view node: two live inherits of the same type on the
same anchor are refused. Two operations positioning the same field on one
view are also refused, and so are two live sets of options on the same
view root. Two live defaults on the same model field are refused
the same way. Company on a bundle is only a filter tag; compiled
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

Some settings live on the view root rather than on a node, and those are
reached from the customization banner instead of a click. A form, list or
kanban can drop its Create, Edit, Delete or Duplicate buttons; a list can
also switch inline editing, allow editing several rows at once, set a
default order and colour rows from a condition; a kanban can drop
quick-create and the create, delete or rename of its columns. Only
options the arch parser of that view type actually reads are accepted,
and a default order is checked against real stored fields, so an option
that would be inert or that would break the list is refused up front.

A table written inside a form is customizable in place: click a column
header of an x2many list, or a field on its card when it renders as a
kanban, to add, place, move, rename, hide or narrow a node of the
**related** model, without leaving the record. Clicking the x2many
field itself also offers the options of that table, so a list of lines
can be made inline editable or lose its Add a line. The operation
targets the related model while the inherit rides on the form that
declares the table, and a field of the record itself keeps anchoring on
the form, so the same name on both sides never collide. When the table
is not written in the form but borrowed from another view, Odoo embeds
it at render time and the client cannot tell; that case is refused with
the model whose list view to open instead, rather than compiled into an
inherit that would match nothing.

The form that opens when a line of that table is expanded is the same
story: if the parent writes a ``<form>`` next to the list, its fields,
pages, groups and buttons are anchors on the related model, and the
inherit still rides on the parent. When that form is borrowed from the
related model, the dialog says so and names the model whose form to
open instead.

A button that calls an action the database already has can be added next
to any field or button of a form, a list or a kanban, including inside a
written table and next to the buttons of a form header. The arch keeps
the XML ID of the action rather than its database id, which is what the
view validator and the client both accept, so the button survives a
reinstall of the module owning the action and the export carries a
readable reference plus the dependency on that module. Anything that is
not an action, or an action without an XML ID, is refused before it is
written, and a second button calling the same action on the same view is
refused as well. Creating the action itself is out of scope: a server
action is written where server actions belong, then bound here.

Pivot and graph views compile too. A pivot measure is clickable like any
other anchor. A graph draws on a canvas, so there is no field node to
click: the banner offers **Graph fields**, a panel of the measures and
groupings the arch already declares. Picking one opens the same dialog
used on a pivot measure. Compile and export are unchanged.

Scope stops at the user interface, and not at all of it. Calendar and
gantt views, creating a model, and report editing are not covered; see
the roadmap. Approvals stay in `base_tier_validation`. Automations stay
in `base.automation` / `automation_oca`.
