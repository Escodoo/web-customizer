Customize the QWeb PDF reports a database already prints — hide a column,
relabel a header, print an extra field, move a block — and ship the result
as a real addon in git.

This is the report surface of `web_customizer`. It reuses the same ledger:
a *bundle* groups *operations*, each operation declares an intent anchored
on a **semantic target**, and a compiler turns it into a plain
`ir.ui.view` inherit of `type=qweb`. Applied bundles export as a standalone
addon that does not depend on the authoring tool at runtime.

What it does not do is store the rendered HTML of the report. Odoo Studio
writes the whole document back as one giant XPath diff, which is why a core
template moving on upgrade takes the customization with it. Here the intent
outlives the artifact: on `-u`, anchors are re-resolved and only a genuinely
missing one is reported as `broken`, with a reason.

## Anchors

A report node is targeted by what the core template already declares, in
this order:

1. `name` on the node (`invoice_date`, `th_quantity`, `td_subtotal`)
2. the `t-field` expression it prints (`o.invoice_date`, `line.quantity`)

Free XPath, translatable text and Bootstrap classes are not anchors: the
first survives nothing, the second changes with the language, the third
changes with the theme. A node that is not unique in the combined arch
leaves the operation `broken` unless an occurrence is set.

The target is the **document** template (`account.report_invoice_document`,
`sale.report_saleorder_document`), never the wrapper that only iterates the
records and calls it. Aiming at a wrapper is refused, with the name of the
document to use instead.

## Operations

- **Hide** — the node stops rendering (`t-if="False"`), so a column, an
  information block or an extra line disappears from the PDF.
- **Rename** — the static label next to a named node is replaced. A node
  that prints a record value has no label, and renaming it is refused.
- **Place** — a QWeb expression is printed before, after or inside the
  anchored node. Next to a table cell it arrives as a cell of the same
  tag. The field itself is still created by `add_field` in `web_customizer`.
- **Move** — the node the template already declares is relocated. A source
  that is missing, or declared more than once, is reported instead of
  compiled into an inherit the renderer would choke on.

Two live operations of the same type on the same anchor of the same
template are refused, and so are two placements of the same expression.

Out of scope on purpose: creating a report from scratch, cloning an action
with its template, editing a dynamic `t-call`, the company layout
(`web.external_layout_*`) and the paper format. Those change every PDF the
company prints, which is a decision, not a customization.
