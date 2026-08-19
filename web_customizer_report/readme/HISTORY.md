## 18.0.1.0.0

First Alpha.

- QWeb document templates are a view type of the customization ledger, so
  a report operation is written, applied, health-checked and exported like
  any other one.
- Nodes are anchored on the `name` the core template carries or on the
  `t-field` expression they print.
- Hide, rename, place and move compile into a single `ir.ui.view` inherit
  of `type=qweb` per operation.
- Aiming at the wrapper template instead of the document is refused, with
  the document to use instead.
- The export writes report inherits with a stable key and depends on the
  module owning the template.
