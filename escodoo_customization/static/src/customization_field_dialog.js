import {Component, onWillStart, useState} from "@odoo/owl";
import {browser} from "@web/core/browser/browser";
import {Dialog} from "@web/core/dialog/dialog";
import {_t} from "@web/core/l10n/translation";
import {RecordSelector} from "@web/core/record_selectors/record_selector";
import {MultiRecordSelector} from "@web/core/record_selectors/multi_record_selector";
import {useService} from "@web/core/utils/hooks";

const FIELD_TYPES = [
    ["char", "Char"],
    ["text", "Text"],
    ["boolean", "Boolean"],
    ["integer", "Integer"],
    ["float", "Float"],
    ["date", "Date"],
    ["datetime", "Datetime"],
    ["selection", "Selection"],
    ["many2one", "Many2one"],
    ["many2many", "Many2many"],
    ["monetary", "Monetary"],
    ["binary", "Binary"],
];

const FIELD_WIDGETS = [
    "badge",
    "boolean_toggle",
    "CopyClipboardChar",
    "email",
    "handle",
    "html",
    "image",
    "many2many_checkboxes",
    "many2many_tags",
    "many2one_avatar",
    "percentage",
    "phone",
    "priority",
    "progressbar",
    "radio",
    "remaining_days",
    "statusbar",
    "url",
];

export class CustomizationFieldDialog extends Component {
    static template = "escodoo_customization.FieldDialog";
    static components = {Dialog, RecordSelector, MultiRecordSelector};
    static props = {
        close: Function,
        fieldName: String,
        fieldLabel: {type: String, optional: true},
        model: {type: String, optional: true},
        viewId: {type: [Number, Boolean], optional: true},
        viewType: {type: String, optional: true},
        anchorKind: {type: String, optional: true},
        anchorString: {type: String, optional: true},
        menuId: {type: Number, optional: true},
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.fieldTypes = FIELD_TYPES;
        this.fieldWidgets = FIELD_WIDGETS;
        this.anchorKind = this.props.anchorKind || "field";
        this.state = useState({
            bundles: [],
            bundleId: false,
            action:
                this.anchorKind === "button" || this.anchorKind === "menu"
                    ? "hide"
                    : "add_after",
            ttype: "char",
            string: "",
            name: "",
            relation: "",
            newLabel: "",
            related: "",
            storeRelated: false,
            existingFieldId: false,
            existingFieldName: "",
            actionId: false,
            targetMenuId: false,
            widget: "",
            groupIds: [],
            modInvisible: "",
            modReadonly: "",
            modRequired: "",
            apply: true,
            busy: false,
            selectionOptions: "",
            currencyField: "",
            anchorCount: 0,
            anchorUnique: true,
            candidates: [],
            anchorIndex: 0,
            anchorPage: "",
        });
        onWillStart(async () => {
            const info = await this.orm.call("customization.bundle", "get_ui_context", [
                this.props.viewId || false,
                this.props.anchorString ? false : this.props.fieldName,
                this.anchorKind,
                this.props.anchorString || false,
            ]);
            this.state.bundles = info.bundles || [];
            this.state.anchorCount = info.anchor_count || 0;
            this.state.anchorUnique = Boolean(info.anchor_unique);
            this.state.candidates = info.candidates || [];
            if (this.state.candidates.length) {
                this.state.anchorIndex = this.state.candidates[0].index;
                this.state.anchorPage = this.state.candidates[0].page || "";
            }
            if (this.state.bundles.length) {
                this.state.bundleId = this.state.bundles[0].id;
            }
        });
    }

    get ttypeDataLossHint() {
        return _t(
            "Changing this type later and clicking Re-apply deletes values already stored in the field."
        );
    }

    get title() {
        const label = this.props.fieldLabel || this.props.fieldName;
        if (this.anchorKind === "page") {
            return _t("Customize page %s", label);
        }
        if (this.anchorKind === "group") {
            return _t("Customize group %s", label);
        }
        if (this.anchorKind === "button") {
            if (this.props.viewType === "kanban") {
                return _t("Customize kanban button %s", label);
            }
            return _t("Customize button %s", label);
        }
        if (this.anchorKind === "menu") {
            return _t("Customize menu %s", label);
        }
        if (this.props.viewType === "list") {
            return _t("Customize list field %s", label);
        }
        if (this.props.viewType === "kanban") {
            return _t("Customize kanban field %s", label);
        }
        if (this.props.viewType === "search") {
            return _t("Customize search field %s", label);
        }
        return _t("Customize field %s", label);
    }

    get actions() {
        if (this.anchorKind === "page") {
            return [
                {value: "add_after", label: _t("Add field in this page")},
                {value: "place_after", label: _t("Place existing field in this page")},
                {value: "add_page", label: _t("Add page after this one")},
                {value: "add_group", label: _t("Add group in this page")},
                {value: "hide", label: _t("Hide this page")},
                {value: "rename", label: _t("Change page title")},
            ];
        }
        if (this.anchorKind === "group") {
            return [
                {value: "add_after", label: _t("Add field in this group")},
                {
                    value: "place_after",
                    label: _t("Place existing field in this group"),
                },
                {value: "add_group", label: _t("Add group after this one")},
                {value: "hide", label: _t("Hide this group")},
                {value: "rename", label: _t("Change group title")},
            ];
        }
        if (this.anchorKind === "button") {
            return [
                {value: "hide", label: _t("Hide this button")},
                {value: "rename", label: _t("Change label")},
                {value: "set_groups", label: _t("Restrict to groups")},
                {value: "set_modifier", label: _t("Set modifiers")},
            ];
        }
        if (this.anchorKind === "progressbar") {
            return [{value: "hide", label: _t("Hide this progressbar")}];
        }
        if (this.anchorKind === "menu") {
            return [
                {value: "hide", label: _t("Hide this menu")},
                {value: "rename", label: _t("Change label")},
                {value: "set_groups", label: _t("Restrict to groups")},
                {value: "add_menu", label: _t("Add menu after this one")},
                {value: "add_submenu", label: _t("Add submenu")},
                {value: "move_menu", label: _t("Move after another menu")},
                {
                    value: "move_as_submenu",
                    label: _t("Move as submenu of another menu"),
                },
            ];
        }
        const fieldActions = [
            {value: "add_after", label: _t("Add field after this one")},
            {value: "place_after", label: _t("Place existing field after this one")},
            {value: "hide", label: _t("Hide this field")},
            {value: "rename", label: _t("Change label")},
            {value: "set_widget", label: _t("Set widget")},
            {value: "set_groups", label: _t("Restrict to groups")},
            {value: "set_modifier", label: _t("Set modifiers")},
        ];
        if ((this.props.viewType || "form") === "form") {
            fieldActions.splice(2, 0, {
                value: "add_group",
                label: _t("Add group after this one"),
            });
            fieldActions.splice(3, 0, {
                value: "add_page",
                label: _t("Add page after this one"),
            });
        }
        return fieldActions;
    }

    get existingFieldDomain() {
        return [
            ["model", "=", this.props.model],
            ["name", "!=", this.props.fieldName],
        ];
    }

    get destinationMenuDomain() {
        const domain = [];
        if (this.props.menuId) {
            domain.push(["id", "!=", this.props.menuId]);
        }
        return domain;
    }

    notifyError(message) {
        this.notification.add(message, {type: "danger"});
    }

    onBundleChange(ev) {
        this.state.bundleId = parseInt(ev.target.value, 10) || false;
    }

    onCandidateChange(ev) {
        const index = parseInt(ev.target.value, 10);
        const candidate = this.state.candidates.find((item) => item.index === index);
        this.state.anchorIndex = Number.isNaN(index) ? 0 : index;
        this.state.anchorPage = candidate?.page || "";
    }

    anchorQualifier() {
        if (this.state.candidates.length <= 1) {
            return {};
        }
        const extra = {anchor_index: this.state.anchorIndex};
        if (this.state.anchorPage) {
            extra.anchor_page = this.state.anchorPage;
        }
        return extra;
    }

    async onExistingFieldUpdate(resId) {
        this.state.existingFieldId = resId || false;
        this.state.existingFieldName = "";
        if (!resId) {
            return;
        }
        const [data] = await this.orm.read("ir.model.fields", [resId], ["name"]);
        this.state.existingFieldName = data?.name || "";
    }

    onWindowActionUpdate(resId) {
        this.state.actionId = resId || false;
    }

    onTargetMenuUpdate(resId) {
        this.state.targetMenuId = resId || false;
    }

    onGroupsUpdate(resIds) {
        this.state.groupIds = resIds || [];
    }

    parseSelectionOptions(text) {
        const options = [];
        for (const rawLine of (text || "").split("\n")) {
            const line = rawLine.trim();
            if (!line) {
                continue;
            }
            const colon = line.indexOf(":");
            const comma = line.indexOf(",");
            const sepIndex = colon >= 0 ? colon : comma;
            if (sepIndex < 0) {
                options.push([line, line]);
                continue;
            }
            const value = line.slice(0, sepIndex).trim();
            const label = line.slice(sepIndex + 1).trim() || value;
            if (value) {
                options.push([value, label]);
            }
        }
        return options;
    }

    payloadForAddAfter() {
        const payload = {string: this.state.string};
        if (this.state.name) {
            payload.name = this.state.name;
        }
        if (this.state.related) {
            payload.related = this.state.related;
            payload.store = this.state.storeRelated;
            return payload;
        }
        payload.ttype = this.state.ttype;
        if (["many2one", "many2many"].includes(this.state.ttype)) {
            payload.relation = this.state.relation;
        }
        if (this.state.ttype === "selection") {
            const selection = this.parseSelectionOptions(this.state.selectionOptions);
            if (!selection.length) {
                this.notifyError(_t("Add at least one selection option."));
                return false;
            }
            payload.selection = selection;
        }
        if (this.state.ttype === "monetary" && this.state.currencyField) {
            payload.currency_field = this.state.currencyField;
        }
        return payload;
    }

    payloadForModifiers() {
        const modifiers = {};
        for (const [stateKey, attr] of [
            ["modInvisible", "invisible"],
            ["modReadonly", "readonly"],
            ["modRequired", "required"],
        ]) {
            const value = this.state[stateKey].trim();
            if (value) {
                modifiers[attr] = value;
            }
        }
        if (!Object.keys(modifiers).length) {
            this.notifyError(_t("Set at least one modifier."));
            return false;
        }
        return {modifiers};
    }

    payloadForAction() {
        const action = this.state.action;
        if (action === "add_after") {
            return this.payloadForAddAfter();
        }
        if (action === "place_after") {
            if (!this.state.existingFieldName) {
                this.notifyError(_t("Select an existing field to place."));
                return false;
            }
            return {field_name: this.state.existingFieldName};
        }
        if (action === "rename") {
            return {string: this.state.newLabel};
        }
        if (action === "add_page" || action === "add_group") {
            const string = this.state.string.trim();
            if (!string) {
                this.notifyError(_t("A label is required."));
                return false;
            }
            const payload = {string};
            if (this.state.name) {
                payload.name = this.state.name;
            }
            return payload;
        }
        if (action === "move_menu" || action === "move_as_submenu") {
            if (!this.state.targetMenuId) {
                this.notifyError(_t("Select a destination menu with an XML ID."));
                return false;
            }
            return {target_menu_id: this.state.targetMenuId};
        }
        if (action === "add_menu" || action === "add_submenu") {
            const string = this.state.string.trim();
            if (!string) {
                this.notifyError(_t("A label is required."));
                return false;
            }
            if (!this.state.actionId) {
                this.notifyError(_t("Select a window action with an XML ID."));
                return false;
            }
            const payload = {string, action_id: this.state.actionId};
            if (this.state.name) {
                payload.name = this.state.name;
            }
            return payload;
        }
        if (action === "set_widget") {
            const widget = this.state.widget.trim();
            if (!widget) {
                this.notifyError(_t("Enter a widget name."));
                return false;
            }
            return {widget};
        }
        if (action === "set_groups") {
            if (!this.state.groupIds.length) {
                this.notifyError(_t("Select at least one group."));
                return false;
            }
            return {group_ids: this.state.groupIds};
        }
        if (action === "set_modifier") {
            return this.payloadForModifiers();
        }
        return {};
    }

    async onApply() {
        if (this.state.busy) {
            return;
        }
        if (!this.state.bundleId) {
            this.notifyError(_t("Create a customization bundle first."));
            return;
        }
        const payload = this.payloadForAction();
        if (payload === false) {
            return;
        }
        this.state.busy = true;
        try {
            const params = {
                bundle_id: this.state.bundleId,
                action: this.state.action,
                model: this.props.model,
                view_id: this.props.viewId || false,
                view_type: this.props.viewType || "form",
                anchor_name: this.props.anchorString ? false : this.props.fieldName,
                anchor_kind: this.anchorKind,
                anchor_string: this.props.anchorString || false,
                menu_id: this.props.menuId || false,
                ...this.anchorQualifier(),
                payload,
                apply: this.state.apply,
            };
            const result = await this.orm.call(
                "customization.bundle",
                "create_from_ui",
                [params]
            );
            if (result.broken && result.broken.length) {
                this.notification.add(
                    result.broken[0].reason || _t("The operation is broken."),
                    {
                        type: "danger",
                        sticky: true,
                    }
                );
                return;
            }
            this.notification.add(_t("Customization applied."), {type: "success"});
            this.props.close();
            if (result.reload) {
                browser.location.reload();
            }
        } finally {
            this.state.busy = false;
        }
    }
}
