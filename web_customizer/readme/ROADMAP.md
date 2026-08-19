Known gaps, ordered by what is worth closing first. Proposals are welcome.

Next:

- A pivot or graph whose arch declares no field has nothing to anchor on,
  so those views cannot be customized until one field exists. The view
  root is an anchor now, but it only carries option writes; placing a
  first field inside it still has to be designed.
- A button binds an action that already exists; writing the server action
  itself is not offered, and neither is a button calling a model method,
  since a method name cannot be validated against user intent the way an
  XML ID can.
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
