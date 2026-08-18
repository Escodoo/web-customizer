Known gaps, ordered by what is worth closing first. Proposals are welcome.

Next:

- Pivot and graph anchors. Both views are described by measures and
  groupings rather than by a tree of nodes, so they fit the existing
  anchor model at a low cost.
- Free XPath anchors stay in the model for export compatibility but are
  not offered in the systray dialog.

Later:

- Calendar and gantt anchors, which need the date field pairs those views
  depend on to be resolved before a node can be targeted.
- Creating a model together with its menu and window action, so a bundle
  can add an entity instead of only extending an existing one.

Deliberately out of this addon:

- Report editing. It is a large surface with anchor semantics of its own
  and belongs in a separate ``web_customizer_report`` addon rather than
  in this one.
- Approvals and automations, which already have community answers in
  ``base_tier_validation`` and ``base.automation`` / ``automation_oca``.
