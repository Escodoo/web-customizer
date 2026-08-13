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

export class CustomizationFieldDialog extends Component {
    static template = "escodoo_customization.FieldDialog";
    static components = {Dialog, RecordSelector};
    static props = {
        close: Function,
        fieldName: String,
        fieldLabel: {type: String, optional: true},
        model: String,
        viewId: Number,
        viewType: {type: String, optional: true},
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.fieldTypes = FIELD_TYPES;
        this.state = useState({
            bundles: [],
            bundleId: false,
            action: "add_after",
            ttype: "char",
            string: "",
            name: "",
            relation: "",
            newLabel: "",
            existingFieldId: false,
            existingFieldName: "",
            apply: true,
            busy: false,
            anchorCount: 0,
            anchorUnique: true,
        });
        onWillStart(async () => {
            const info = await this.orm.call("customization.bundle", "get_ui_context", [
                this.props.viewId,
                this.props.fieldName,
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
        return _t("Customize field %s", this.props.fieldLabel || this.props.fieldName);
    }

    get existingFieldDomain() {
        return [
            ["model", "=", this.props.model],
            ["name", "!=", this.props.fieldName],
        ];
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

    async onApply() {
        if (this.state.busy) {
            return;
        }
        if (!this.state.bundleId) {
            this.notification.add(_t("Create a customization bundle first."), {
                type: "danger",
            });
            return;
        }
        const payload = {};
        if (this.state.action === "add_after") {
            payload.ttype = this.state.ttype;
            payload.string = this.state.string;
            if (this.state.name) {
                payload.name = this.state.name;
            }
            if (["many2one", "many2many"].includes(this.state.ttype)) {
                payload.relation = this.state.relation;
            }
        } else if (this.state.action === "place_after") {
            if (!this.state.existingFieldName) {
                this.notification.add(_t("Select an existing field to place."), {
                    type: "danger",
                });
                return;
            }
            payload.field_name = this.state.existingFieldName;
        } else if (this.state.action === "rename") {
            payload.string = this.state.newLabel;
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
