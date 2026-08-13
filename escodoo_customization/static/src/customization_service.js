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
                        _t(
                            "Customization mode is on. Click a field, page, button, list column or search field."
                        ),
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

export function isListRoot(component) {
    const config = component.env.config || {};
    return config.viewType === "list" && Boolean(config.viewId);
}

function fieldLabelOf(component, fieldName, extra) {
    return (
        extra.fieldLabel ||
        component.props.string ||
        component.props.record?.fields?.[fieldName]?.string ||
        fieldName
    );
}

function customizationTarget(component, extra) {
    const viewType = extra.viewType || component.env.config?.viewType || "form";
    if (viewType === "form" && !isFormRootField(component)) {
        return null;
    }
    if (viewType === "list" && !isListRoot(component)) {
        return null;
    }
    const viewId = extra.viewId || component.env.config?.viewId;
    if (!viewId) {
        return null;
    }
    return {viewType, viewId};
}

export function openCustomizationFor(component, fieldName, ev, extra = {}) {
    const customization = component.customization;
    if (!customization?.state.enabled || !fieldName) {
        return false;
    }
    const target = customizationTarget(component, extra);
    if (!target) {
        return false;
    }
    if (ev) {
        ev.preventDefault();
        ev.stopPropagation();
    }
    const record = formRecord(component);
    customization.openFieldDialog({
        fieldName,
        fieldLabel: fieldLabelOf(component, fieldName, extra),
        model: extra.model || record?.resModel,
        viewId: target.viewId,
        viewType: target.viewType,
        anchorKind: extra.anchorKind || "field",
    });
    return true;
}
