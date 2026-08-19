Known gaps, ordered by what is worth closing first.

Next:

- No in-place UI yet. Operations are written from the backend form. The
  honest surface is the HTML preview of the report (`qweb-html`) with the
  `name` and `t-field` nodes clickable, the analogue of the graph field
  panel, not a WYSIWYG canvas.
- A table column still takes two operations, one for the header and one
  for the cell. Pairing them behind a single intent needs the two anchors
  to be resolved together.
- A placement inside a line loop is checked for syntax and for the
  variable, but not against a model: the comodel a `t-foreach` iterates
  cannot be resolved without evaluating the arch.

Deliberately out of this addon:

- The company layout (`web.external_layout_*`) and the paper format. They
  change every PDF the company prints; that is a setting, not a
  per-report customization.
- Creating a report from scratch, or cloning an action together with its
  template. A new report is written where addons are written.
- Editing a dynamic `t-call`, which decides at render time which template
  runs and therefore has no anchor to resolve up front.
