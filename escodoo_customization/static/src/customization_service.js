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
                        _t("Customization mode is on. Click a field, page or button."),
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

function formRecord(component) {
    return component.props.record || component.env.model?.root;
}

export function isFormRootField(component) {
    const config = component.env.config || {};
    if (config.viewType !== "form" || !config.viewId) {
        return false;
    }
    const record = formRecord(component);
    if (record?.model && record !== record.model.root) {
        return false;
    }
    return true;
}

export function openCustomizationFor(component, fieldName, ev, extra = {}) {
    const customization = component.customization;
    if (!customization?.state.enabled || !isFormRootField(component) || !fieldName) {
        return false;
    }
    ev.preventDefault();
    ev.stopPropagation();
    const record = formRecord(component);
    customization.openFieldDialog({
        fieldName,
        fieldLabel:
            extra.fieldLabel ||
            component.props.string ||
            component.props.record?.fields?.[fieldName]?.string ||
            fieldName,
        model: record?.resModel,
        viewId: component.env.config.viewId,
        viewType: component.env.config.viewType || "form",
        anchorKind: extra.anchorKind || "field",
    });
    return true;
}
