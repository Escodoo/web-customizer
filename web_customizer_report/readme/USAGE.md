Report operations live in the same ledger as the rest, so they are written
from **Settings → Technical → Customizations** on the bundle of the client.

Add an operation and fill:

- **View**: the document template, for example `account.report_invoice_document`.
  The wrapper (`account.report_invoice`) is refused.
- **View type**: *Report (QWeb)*. This is what routes the operation to the
  report compiler.
- **Anchor kind**: *Field* to anchor on the `name` of the node, or
  *Report Value* to anchor on its `t-field` expression.
- **Anchor name**: `td_quantity`, `invoice_line_table`, `o.invoice_date`, …
- **Anchor occurrence**: only when the name is not unique in the template.

Then pick the type:

| Type | What to fill |
|---|---|
| Hide Field | nothing |
| Set Label | *Label* — the new static text |
| Place Field | *Field To Place* — a QWeb expression such as `o.x_cust_po_number` |
| Move Field | *Field To Place* — the `name` of the node to relocate |

Click **Apply**. A failure never writes a half-broken inherit: the
operation turns `broken` and names what it could not resolve.

## Finding the anchors

Open the template from **Settings → Technical → User Interface → Views**
and read the `name` attributes the core already carries. The invoice
document names its date block (`invoice_date`), its table
(`invoice_line_table`), every header cell (`th_description`,
`th_quantity`, …) and every line cell (`td_quantity`, `td_subtotal`, …).
The sale order document follows the same convention.

## Adding a column

A table column is two nodes: the header and the cell. Hiding one leaves
the other, so hiding a column takes two operations (`th_quantity` and
`td_quantity`), and so does adding one. Placing next to a `<td>` or a
`<th>` emits a cell of the same tag, so the row keeps its shape.

## Export

Export the bundle as usual. Report inherits land in
`views/inherited_views.xml` as `ir.ui.view` records of `type=qweb`, with
`inherit_id` pointing at the core template by XML ID, and the manifest
depends on the module that owns it (`account`, `sale`, …). The exported
addon installs without `web_customizer` or this module.
