import {combineAttributes} from "@web/core/utils/xml";
import {patch} from "@web/core/utils/patch";
import {KanbanCompiler} from "@web/views/kanban/kanban_compiler";
import {KanbanRecord} from "@web/views/kanban/kanban_record";
import {
    isKanbanRoot,
    openCustomizationFor,
    useCustomizationService,
} from "./customization_service";

patch(KanbanCompiler.prototype, {
    compileField(el, params) {
        const compiled = super.compileField(el, params);
        const fieldName = el.getAttribute("name") || "";
        if (!/^\w+$/.test(fieldName)) {
            return compiled;
        }
        const tag = (compiled.tagName || "").toLowerCase();
        if (tag !== "span") {
            return compiled;
        }
        compiled.setAttribute(
            "t-on-click",
            `(ev) => __comp__.onCustomizationFieldClick(ev, ${JSON.stringify(fieldName)})`
        );
        combineAttributes(compiled, "class", ["o_esc_kanban_field"]);
        return compiled;
    },
    compileButton(el, params) {
        const name = el.getAttribute("name") || "";
        const type = el.getAttribute("type") || "";
        const label = el.getAttribute("string") || name || type;
        const compiled = super.compileButton(el, params);
        const anchor = /^\w+$/.test(name) ? name : /^\w+$/.test(type) ? type : "";
        if (!anchor) {
            return compiled;
        }
        const tag = (compiled.tagName || "").toLowerCase();
        if (tag === "viewbutton") {
            return compiled;
        }
        const previous = compiled.getAttribute("t-on-click") || "";
        const fallback = previous || "() => {}";
        compiled.setAttribute(
            "t-on-click",
            `(ev) => __comp__.onCustomizationButtonClick(ev, ${JSON.stringify(anchor)}, ${JSON.stringify(label)}, () => {(${fallback})()})`
        );
        combineAttributes(compiled, "class", ["o_esc_kanban_button"]);
        return compiled;
    },
});

patch(KanbanRecord.prototype, {
    setup() {
        super.setup(...arguments);
        this.customization = useCustomizationService();
    },
    getRecordClasses() {
        const classes = super.getRecordClasses();
        if (this.customization?.state.enabled && isKanbanRoot(this)) {
            return `${classes} o_esc_customization_mode`.trim();
        }
        return classes;
    },
    onCustomizationFieldClick(ev, fieldName) {
        if (!this.customization?.state.enabled || !isKanbanRoot(this)) {
            return;
        }
        const label = this.props.record?.fields?.[fieldName]?.string || fieldName;
        openCustomizationFor(this, fieldName, ev, {
            viewType: "kanban",
            fieldLabel: label,
            model: this.props.record?.resModel,
        });
    },
    onCustomizationButtonClick(ev, anchor, label, original) {
        if (
            this.customization?.state.enabled &&
            isKanbanRoot(this) &&
            openCustomizationFor(this, anchor, ev, {
                viewType: "kanban",
                anchorKind: "button",
                fieldLabel: label || anchor,
                model: this.props.record?.resModel,
            })
        ) {
            return;
        }
        if (typeof original === "function") {
            original();
        }
    },
});
