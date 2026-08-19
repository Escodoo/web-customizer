import {Component, onWillStart, useState} from "@odoo/owl";
import {Dialog} from "@web/core/dialog/dialog";
import {useCustomizationService} from "./customization_service";
import {_t} from "@web/core/l10n/translation";
import {useService} from "@web/core/utils/hooks";

const ROLE_LABELS = {
    measure: () => _t("Measure"),
    groupby: () => _t("Grouping"),
};

export class GraphFieldsDialog extends Component {
    static template = "web_customizer.GraphFieldsDialog";
    static components = {Dialog};
    static props = {
        close: Function,
        viewId: Number,
        model: String,
        viewType: {type: String, optional: true},
    };

    setup() {
        this.orm = useService("orm");
        this.customization = useCustomizationService();
        this.state = useState({
            fields: [],
            loadError: "",
        });
        onWillStart(async () => {
            try {
                this.state.fields = await this.orm.call(
                    "customization.bundle",
                    "list_arch_fields",
                    [this.props.viewId]
                );
            } catch (error) {
                this.state.loadError =
                    error.data?.message ||
                    error.message ||
                    _t("Could not load the graph fields.");
            }
        });
    }

    get title() {
        return _t("Graph fields");
    }

    get emptyMessage() {
        return _t(
            "This graph has no field in its arch, so there is nothing to customize yet."
        );
    }

    get hint() {
        return _t(
            "The chart is drawn on a canvas. Pick a field the view already declares."
        );
    }

    get closeLabel() {
        return _t("Close");
    }

    roleLabel(role) {
        const label = ROLE_LABELS[role];
        return label ? label() : role || "";
    }

    openField(field) {
        this.props.close();
        this.customization.openFieldDialog({
            fieldName: field.name,
            fieldLabel: field.string || field.name,
            model: this.props.model,
            viewId: this.props.viewId,
            viewType: this.props.viewType || "graph",
            anchorKind: "field",
        });
    }
}
