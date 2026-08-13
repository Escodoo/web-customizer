import {reactive} from "@odoo/owl";
import {_t} from "@web/core/l10n/translation";
import {registry} from "@web/core/registry";
import {CustomizationFieldDialog} from "./customization_field_dialog";

export const customizationService = {
    dependencies: ["dialog", "notification"],
    start(env, {dialog, notification}) {
        const state = reactive({enabled: false});
        return {
            state,
            toggle() {
                state.enabled = !state.enabled;
                if (state.enabled) {
                    notification.add(
                        _t("Customization mode is on. Click a field on the form."),
                        {type: "info"}
                    );
                }
            },
            openFieldDialog(info) {
                dialog.add(CustomizationFieldDialog, info);
            },
        };
    },
};

registry.category("services").add("escodoo_customization", customizationService);

export function isFormRootField(component) {
    const record = component.props.record;
    const config = component.env.config || {};
    return Boolean(
        config.viewType === "form" &&
            config.viewId &&
            record &&
            record.model &&
            record === record.model.root
    );
}

export function openCustomizationFor(component, fieldName, ev) {
    const customization = component.customization;
    if (!customization?.state.enabled || !isFormRootField(component) || !fieldName) {
        return false;
    }
    ev.preventDefault();
    ev.stopPropagation();
    customization.openFieldDialog({
        fieldName,
        fieldLabel:
            component.props.string ||
            component.props.record?.fields?.[fieldName]?.string ||
            fieldName,
        model: component.props.record.resModel,
        viewId: component.env.config.viewId,
        viewType: component.env.config.viewType || "form",
    });
    return true;
}
