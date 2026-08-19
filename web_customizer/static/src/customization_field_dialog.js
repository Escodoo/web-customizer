import {Component, onWillStart, useState} from "@odoo/owl";
import {Dialog} from "@web/core/dialog/dialog";
import {MultiRecordSelector} from "@web/core/record_selectors/multi_record_selector";
import {RecordSelector} from "@web/core/record_selectors/record_selector";
import {_t} from "@web/core/l10n/translation";
import {browser} from "@web/core/browser/browser";
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

// An action without a builder here sends an empty payload, which is what the
// actions carrying their intent in the anchor alone (hide) need.
const ROOT_ACTION_OPTIONS = [
    ["rootCreate", "create"],
    ["rootEdit", "edit"],
    ["rootDelete", "delete"],
    ["rootDuplicate", "duplicate"],
];

const PAYLOAD_BUILDERS = {
    set_view_attribute: "payloadForViewOptions",
    add_after: "payloadForAddAfter",
    place_after: "payloadForExistingField",
    move_after: "payloadForExistingField",
    rename: "payloadForRename",
    add_page: "payloadForLabelledNode",
    add_group: "payloadForLabelledNode",
    add_filter: "payloadForFilter",
    move_menu: "payloadForMenuDestination",
    move_as_submenu: "payloadForMenuDestination",
    add_menu: "payloadForNewMenu",
    add_submenu: "payloadForNewMenu",
    set_widget: "payloadForWidget",
    set_optional: "payloadForOptional",
    set_groups: "payloadForGroups",
    set_modifier: "payloadForModifiers",
};

export class CustomizationFieldDialog extends Component {
    static template = "web_customizer.FieldDialog";
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
        anchorSubview: {type: String, optional: true},
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
            action: this.defaultAction,
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
            optional: "hide",
            rootCreate: "",
            rootEdit: "",
            rootDelete: "",
            rootDuplicate: "",
            rootEditable: "",
            rootDefaultOrder: "",
            rootDecoration: "danger",
            rootDecorationCondition: "",
            filterDomain: "",
            filterGroupBy: "",
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
            subviewInline: true,
            fieldSubview: false,
            loadError: "",
        });
        onWillStart(async () => {
            try {
                this.loadContext(
                    await this.orm.call("customization.bundle", "get_ui_context", [
                        this.props.viewId || false,
                        this.props.anchorString ? false : this.props.fieldName,
                        this.anchorKind,
                        this.props.anchorString || false,
                        this.props.anchorSubview || false,
                    ])
                );
            } catch (error) {
                this.state.loadError =
                    error.data?.message ||
                    error.message ||
                    _t("Could not load customization context.");
            }
        });
    }

    loadContext(info) {
        this.state.bundles = info.bundles || [];
        this.state.anchorCount = info.anchor_count || 0;
        this.state.anchorUnique = Boolean(info.anchor_unique);
        this.state.subviewInline = info.subview_inline !== false;
        this.state.fieldSubview = info.field_subview || false;
        this.state.candidates = info.candidates || [];
        if (this.state.candidates.length) {
            this.state.anchorIndex = this.state.candidates[0].index;
            this.state.anchorPage = this.state.candidates[0].page || "";
        }
        if (this.state.bundles.length) {
            this.state.bundleId = this.state.bundles[0].id;
        }
    }

    get tableTarget() {
        // A click on the x2many field can also mean "options of the table it
        // writes", and those belong to the related model, not to this form.
        return this.anchorKind === "field" ? this.state.fieldSubview : false;
    }

    get targetViewType() {
        if (this.state.action === "set_view_attribute" && this.tableTarget) {
            return this.tableTarget.type;
        }
        return this.props.viewType;
    }

    get isListView() {
        return this.targetViewType === "list";
    }

    get rootActionOptions() {
        const labels = {
            rootCreate: _t("Creating records"),
            rootEdit: _t("Editing records"),
            rootDelete: _t("Deleting records"),
            rootDuplicate: _t("Duplicating records"),
        };
        return ROOT_ACTION_OPTIONS.map(([key, name]) => [key, name, labels[key]]);
    }

    get decorations() {
        return ["bf", "it", "danger", "info", "muted", "primary", "success", "warning"];
    }

    get defaultAction() {
        if (this.anchorKind === "view") {
            return "set_view_attribute";
        }
        if (this.anchorKind === "button" || this.anchorKind === "menu") {
            return "hide";
        }
        return "add_after";
    }

    get ttypeDataLossHint() {
        return _t(
            "Changing this type later and clicking Re-apply deletes values already stored in the field."
        );
    }

    get title() {
        const label = this.props.fieldLabel || this.props.fieldName;
        if (this.anchorKind === "view") {
            return _t("Options of this %s view", this.props.viewType || "");
        }
        if (this.props.anchorSubview) {
            return _t("Customize column %s", label);
        }
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
        if (this.anchorKind === "filter") {
            return _t("Customize filter %s", label);
        }
        if (this.props.viewType === "search") {
            return _t("Customize search field %s", label);
        }
        if (this.props.viewType === "pivot") {
            return _t("Customize pivot measure %s", label);
        }
        return _t("Customize field %s", label);
    }

    get actions() {
        if (this.anchorKind === "view") {
            return [{value: "set_view_attribute", label: _t("Set view options")}];
        }
        if (this.anchorKind === "page") {
            return [
                {value: "add_after", label: _t("Add field in this page")},
                {value: "place_after", label: _t("Place existing field in this page")},
                {value: "move_after", label: _t("Move existing field to this page")},
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
                {value: "move_after", label: _t("Move existing field to this group")},
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
        if (this.anchorKind === "filter") {
            return [
                {value: "add_filter", label: _t("Add filter after this one")},
                {value: "hide", label: _t("Hide this filter")},
                {value: "rename", label: _t("Change label")},
                {value: "set_groups", label: _t("Restrict to groups")},
            ];
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
        if (this.props.viewType === "pivot") {
            // A pivot parser only reads string, widget, invisible and the
            // aggregate role, so modifiers and structure have nothing to act on.
            return [
                {value: "add_after", label: _t("Add measure after this one")},
                {value: "place_after", label: _t("Place existing field as measure")},
                {value: "move_after", label: _t("Move an existing measure here")},
                {value: "hide", label: _t("Hide this measure")},
                {value: "rename", label: _t("Change label")},
                {value: "set_widget", label: _t("Set widget")},
                {value: "set_groups", label: _t("Restrict to groups")},
            ];
        }
        const fieldActions = [
            {value: "add_after", label: _t("Add field after this one")},
            {value: "place_after", label: _t("Place existing field after this one")},
            {value: "move_after", label: _t("Move an existing field here")},
            {value: "hide", label: _t("Hide this field")},
            {value: "rename", label: _t("Change label")},
            {value: "set_widget", label: _t("Set widget")},
            {value: "set_groups", label: _t("Restrict to groups")},
            {value: "set_modifier", label: _t("Set modifiers")},
        ];
        if ((this.props.viewType || "form") === "form") {
            fieldActions.splice(3, 0, {
                value: "add_group",
                label: _t("Add group after this one"),
            });
            fieldActions.splice(4, 0, {
                value: "add_page",
                label: _t("Add page after this one"),
            });
        }
        if (this.props.viewType === "list") {
            fieldActions.splice(3, 0, {
                value: "set_optional",
                label: _t("Make column optional"),
            });
        }
        if (this.props.viewType === "search") {
            fieldActions.splice(3, 0, {
                value: "add_filter",
                label: _t("Add filter after this one"),
            });
        }
        if (this.state.fieldSubview) {
            fieldActions.push({
                value: "set_view_attribute",
                label: _t("Set options of this table"),
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

    requiredLabel(message) {
        const string = this.state.string.trim();
        if (!string) {
            this.notifyError(message);
            return false;
        }
        return string;
    }

    withOptionalName(payload) {
        if (this.state.name) {
            payload.name = this.state.name;
        }
        return payload;
    }

    payloadForExistingField() {
        if (!this.state.existingFieldName) {
            this.notifyError(_t("Select an existing field to place."));
            return false;
        }
        return {field_name: this.state.existingFieldName};
    }

    payloadForRename() {
        return {string: this.state.newLabel};
    }

    payloadForLabelledNode() {
        const string = this.requiredLabel(_t("A label is required."));
        return string && this.withOptionalName({string});
    }

    payloadForFilter() {
        const string = this.requiredLabel(_t("A filter label is required."));
        if (!string) {
            return false;
        }
        const groupBy = this.state.filterGroupBy.trim();
        const domain = this.state.filterDomain.trim();
        if (!groupBy && !domain) {
            this.notifyError(_t("Enter a domain or a field to group by."));
            return false;
        }
        if (groupBy && domain) {
            this.notifyError(_t("A filter carries either a domain or a grouping."));
            return false;
        }
        return {string, domain, group_by: groupBy};
    }

    payloadForMenuDestination() {
        if (!this.state.targetMenuId) {
            this.notifyError(_t("Select a destination menu with an XML ID."));
            return false;
        }
        return {target_menu_id: this.state.targetMenuId};
    }

    payloadForNewMenu() {
        const string = this.requiredLabel(_t("A label is required."));
        if (!string) {
            return false;
        }
        if (!this.state.actionId) {
            this.notifyError(_t("Select a window action with an XML ID."));
            return false;
        }
        return this.withOptionalName({string, action_id: this.state.actionId});
    }

    payloadForWidget() {
        const widget = this.state.widget.trim();
        if (!widget) {
            this.notifyError(_t("Enter a widget name."));
            return false;
        }
        return {widget};
    }

    payloadForOptional() {
        return {optional: this.state.optional};
    }

    payloadForViewOptions() {
        const attributes = {};
        for (const [key, name] of ROOT_ACTION_OPTIONS) {
            if (this.state[key]) {
                attributes[name] = this.state[key];
            }
        }
        if (this.isListView && this.state.rootEditable) {
            // An empty value drops the attribute, turning inline editing off
            // on a list the base view made editable.
            attributes.editable =
                this.state.rootEditable === "off" ? "" : this.state.rootEditable;
        }
        const order = this.state.rootDefaultOrder.trim();
        if (order && this.targetViewType !== "form") {
            attributes.default_order = order;
        }
        const condition = this.state.rootDecorationCondition.trim();
        if (this.isListView && condition) {
            attributes[`decoration-${this.state.rootDecoration}`] = condition;
        }
        if (!Object.keys(attributes).length) {
            this.notifyError(_t("Set at least one view option."));
            return false;
        }
        return {attributes};
    }

    payloadForGroups() {
        if (!this.state.groupIds.length) {
            this.notifyError(_t("Select at least one group."));
            return false;
        }
        return {group_ids: this.state.groupIds};
    }

    payloadForAction() {
        const builder = PAYLOAD_BUILDERS[this.state.action];
        return builder ? this[builder]() : {};
    }

    uiParams(payload) {
        const params = {
            bundle_id: this.state.bundleId,
            action: this.state.action,
            model: this.props.model,
            view_id: this.props.viewId || false,
            view_type: this.props.viewType || "form",
            anchor_name: this.props.anchorString ? false : this.props.fieldName,
            anchor_kind: this.anchorKind,
            anchor_string: this.props.anchorString || false,
            anchor_subview: this.props.anchorSubview || false,
            menu_id: this.props.menuId || false,
            ...this.anchorQualifier(),
            payload,
            apply: this.state.apply,
        };
        if (this.state.action === "set_view_attribute" && this.tableTarget) {
            // The clicked node is the field, but the options land on the
            // table it writes, which belongs to the related model.
            Object.assign(params, {
                model: this.tableTarget.model,
                view_type: this.tableTarget.type,
                anchor_kind: "view",
                anchor_name: false,
                anchor_subview: this.props.fieldName,
                anchor_index: null,
                anchor_page: false,
            });
        }
        return params;
    }

    reportResult(result) {
        const broken = result.broken || [];
        if (broken.length) {
            this.notification.add(broken[0].reason || _t("The operation is broken."), {
                type: "danger",
                sticky: true,
            });
            return;
        }
        this.notification.add(_t("Customization applied."), {type: "success"});
        this.props.close();
        if (result.reload) {
            browser.location.reload();
        }
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
            const result = await this.orm.call(
                "customization.bundle",
                "create_from_ui",
                [this.uiParams(payload)]
            );
            this.reportResult(result);
        } catch (error) {
            this.notifyError(
                error.data?.message ||
                    error.message ||
                    _t("Could not apply customization.")
            );
        } finally {
            this.state.busy = false;
        }
    }
}
