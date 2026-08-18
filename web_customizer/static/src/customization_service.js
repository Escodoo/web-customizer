import {reactive, useState} from "@odoo/owl";
import {CustomizationFieldDialog} from "./customization_field_dialog";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";

export const customizationService = {
    dependencies: ["dialog"],
    start(env, {dialog}) {
        const state = reactive({enabled: false});
        return {
            state,
            toggle() {
                state.enabled = !state.enabled;
                if (typeof document !== "undefined") {
                    document.body.classList.toggle(
                        "o_esc_customization_mode",
                        state.enabled
                    );
                }
            },
            openFieldDialog(info) {
                dialog.add(CustomizationFieldDialog, info);
            },
        };
    },
};

registry.category("services").add("web_customizer", customizationService);

export function useCustomizationService() {
    const customization = useService("web_customizer");
    const state = useState(customization.state);
    return {
        state,
        toggle: () => customization.toggle(),
        openFieldDialog: (info) => customization.openFieldDialog(info),
    };
}

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

export function isKanbanRoot(component) {
    const config = component.env.config || {};
    return config.viewType === "kanban" && Boolean(config.viewId);
}

export function isPivotRoot(component) {
    const config = component.env.config || {};
    return config.viewType === "pivot" && Boolean(config.viewId);
}

export const BUTTON_TYPE_ANCHORS = [
    "edit",
    "open",
    "delete",
    "url",
    "set_cover",
    "archive",
    "unarchive",
];

export function viewButtonAnchor(button) {
    const name = button.clickParams?.name;
    if (name) {
        return String(name);
    }
    const type = button.clickParams?.type;
    if (type && BUTTON_TYPE_ANCHORS.includes(type)) {
        return String(type);
    }
    return "";
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
    if (viewType === "kanban" && !isKanbanRoot(component)) {
        return null;
    }
    if (viewType === "pivot" && !isPivotRoot(component)) {
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
    const anchorString = extra.anchorString || "";
    if (!customization?.state.enabled || !(fieldName || anchorString)) {
        return false;
    }
    const target = customizationTarget(component, extra);
    if (!target) {
        return false;
    }
    if (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        ev.stopImmediatePropagation();
    }
    const record = formRecord(component);
    const name = fieldName || anchorString;
    customization.openFieldDialog({
        fieldName: name,
        fieldLabel: fieldLabelOf(component, name, extra),
        model: extra.model || record?.resModel,
        viewId: target.viewId,
        viewType: target.viewType,
        anchorKind: extra.anchorKind || "field",
        anchorString,
    });
    return true;
}
