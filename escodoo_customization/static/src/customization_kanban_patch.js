import {isKanbanRoot, openCustomizationFor} from "./customization_service";
import {useService} from "@web/core/utils/hooks";
import {patch} from "@web/core/utils/patch";
import {combineAttributes} from "@web/core/utils/xml";
import {KanbanCompiler} from "@web/views/kanban/kanban_compiler";
import {KanbanRecord} from "@web/views/kanban/kanban_record";

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
});

patch(KanbanRecord.prototype, {
    setup() {
        super.setup(...arguments);
        this.customization = useService("escodoo_customization");
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
});
