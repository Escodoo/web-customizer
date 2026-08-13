import {Component, onWillStart, useState} from "@odoo/owl";
import {browser} from "@web/core/browser/browser";
import {Dialog} from "@web/core/dialog/dialog";
import {_t} from "@web/core/l10n/translation";
import {RecordSelector} from "@web/core/record_selectors/record_selector";
import {useService} from "@web/core/utils/hooks";

const FIELD_TYPES = [
    ["char", "Char"],
    ["text", "Text"],
    ["boolean", "Boolean"],
    ["integer", "Integer"],
    ["float", "Float"],
    ["date", "Date"],
    ["datetime", "Datetime"],
    ["many2one", "Many2one"],
    ["many2many", "Many2many"],
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
    static components = {Dialog, RecordSelector};
    static props = {
        close: Function,
        fieldName: String,
        fieldLabel: {type: String, optional: true},
        model: {type: String, optional: true},
        viewId: Number,
        viewType: {type: String, optional: true},
        anchorKind: {type: String, optional: true},
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
            action: this.anchorKind === "button" ? "hide" : "add_after",
            ttype: "char",
            string: "",
            name: "",
            relation: "",
            newLabel: "",
            related: "",
            storeRelated: false,
            existingFieldId: false,
            existingFieldName: "",
            widget: "",
            groups: "",
            modInvisible: "",
            modReadonly: "",
            modRequired: "",
            apply: true,
            busy: false,
            anchorCount: 0,
            anchorUnique: true,
        });
        onWillStart(async () => {
            const info = await this.orm.call("customization.bundle", "get_ui_context", [
                this.props.viewId,
                this.props.fieldName,
                this.anchorKind,
            ]);
            this.state.bundles = info.bundles || [];
            this.state.anchorCount = info.anchor_count || 0;
            this.state.anchorUnique = Boolean(info.anchor_unique);
            if (this.state.bundles.length) {
                this.state.bundleId = this.state.bundles[0].id;
            }
        });
    }

    get title() {
        const label = this.props.fieldLabel || this.props.fieldName;
        if (this.anchorKind === "page") {
            return _t("Customize page %s", label);
        }
        if (this.anchorKind === "button") {
            return _t("Customize button %s", label);
        }
        return _t("Customize field %s", label);
    }

    get actions() {
        if (this.anchorKind === "page") {
            return [
                {value: "add_after", label: _t("Add field in this page")},
                {value: "place_after", label: _t("Place existing field in this page")},
                {value: "hide", label: _t("Hide this page")},
                {value: "rename", label: _t("Change page title")},
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
        return [
            {value: "add_after", label: _t("Add field after this one")},
            {value: "place_after", label: _t("Place existing field after this one")},
            {value: "hide", label: _t("Hide this field")},
            {value: "rename", label: _t("Change label")},
            {value: "set_widget", label: _t("Set widget")},
            {value: "set_groups", label: _t("Restrict to groups")},
            {value: "set_modifier", label: _t("Set modifiers")},
        ];
    }

    get existingFieldDomain() {
        return [
            ["model", "=", this.props.model],
            ["name", "!=", this.props.fieldName],
        ];
    }

    notifyError(message) {
        this.notification.add(message, {type: "danger"});
    }

    onBundleChange(ev) {
        this.state.bundleId = parseInt(ev.target.value, 10) || false;
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
        if (action === "set_widget") {
            const widget = this.state.widget.trim();
            if (!widget) {
                this.notifyError(_t("Enter a widget name."));
                return false;
            }
            return {widget};
        }
        if (action === "set_groups") {
            const groups = this.state.groups.trim();
            if (!groups) {
                this.notifyError(_t("Enter at least one group XML ID."));
                return false;
            }
            return {groups};
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
            const result = await this.orm.call(
                "customization.bundle",
                "create_from_ui",
                [
                    {
                        bundle_id: this.state.bundleId,
                        action: this.state.action,
                        model: this.props.model,
                        view_id: this.props.viewId,
                        view_type: this.props.viewType || "form",
                        anchor_name: this.props.fieldName,
                        anchor_kind: this.anchorKind,
                        payload,
                        apply: this.state.apply,
                    },
                ]
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
