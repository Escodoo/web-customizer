import {
    isKanbanRoot,
    openCustomizationFor,
    useCustomizationService,
} from "./customization_service";
import {KanbanCompiler} from "@web/views/kanban/kanban_compiler";
import {KanbanHeader} from "@web/views/kanban/kanban_header";
import {KanbanRecord} from "@web/views/kanban/kanban_record";
import {combineAttributes} from "@web/core/utils/xml";
import {patch} from "@web/core/utils/patch";
import {useEffect} from "@odoo/owl";

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
            "t-on-click.capture",
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
        compiled.removeAttribute("t-on-click");
        compiled.setAttribute(
            "t-on-click.capture",
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
    get customizationSubview() {
        return this.env.customizationSubview || null;
    },
    get customizationAnchorable() {
        return Boolean(isKanbanRoot(this) || this.customizationSubview);
    },
    getRecordClasses() {
        const classes = super.getRecordClasses();
        if (this.customization?.state.enabled && this.customizationAnchorable) {
            return `${classes} o_esc_customization_mode`.trim();
        }
        return classes;
    },
    onGlobalClick(ev) {
        if (this.customization?.state.enabled && this.customizationAnchorable) {
            ev.preventDefault();
            ev.stopPropagation();
            return;
        }
        return super.onGlobalClick(ev);
    },
    onCustomizationFieldClick(ev, fieldName) {
        if (!this.customization?.state.enabled || !this.customizationAnchorable) {
            return;
        }
        const label = this.props.record?.fields?.[fieldName]?.string || fieldName;
        openCustomizationFor(this, fieldName, ev, {
            viewType: "kanban",
            fieldLabel: label,
            model: this.props.record?.resModel,
            anchorSubview: this.customizationSubview?.name,
        });
    },
    onCustomizationButtonClick(ev, anchor, label, original) {
        if (
            this.customization?.state.enabled &&
            this.customizationAnchorable &&
            openCustomizationFor(this, anchor, ev, {
                viewType: "kanban",
                anchorKind: "button",
                fieldLabel: label || anchor,
                model: this.props.record?.resModel,
                anchorSubview: this.customizationSubview?.name,
            })
        ) {
            return;
        }
        if (typeof original === "function") {
            original();
        }
    },
});

patch(KanbanHeader.prototype, {
    setup() {
        super.setup(...arguments);
        this.customization = useCustomizationService();
        useEffect(
            () => {
                const el = this.rootRef?.el;
                if (!el) {
                    return;
                }
                const onClick = (ev) => this.onCustomizationProgressClick(ev);
                el.addEventListener("click", onClick, true);
                return () => el.removeEventListener("click", onClick, true);
            },
            () => [this.rootRef?.el]
        );
    },
    onCustomizationProgressClick(ev) {
        if (!this.customization?.state.enabled || !isKanbanRoot(this)) {
            return;
        }
        const counter = ev.target.closest(".o_kanban_counter");
        if (!counter || !this.rootRef?.el.contains(counter)) {
            return;
        }
        const fieldName = this.props.progressBarState?.progressAttributes?.fieldName;
        if (!fieldName) {
            return;
        }
        openCustomizationFor(this, fieldName, ev, {
            viewType: "kanban",
            anchorKind: "progressbar",
            fieldLabel: fieldName,
            model: this.props.list?.resModel,
        });
    },
});
