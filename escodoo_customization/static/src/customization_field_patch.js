import {
    isFormRootField,
    isKanbanRoot,
    openCustomizationFor,
} from "./customization_service";
import {Notebook} from "@web/core/notebook/notebook";
import {useService} from "@web/core/utils/hooks";
import {patch} from "@web/core/utils/patch";
import {Field} from "@web/views/fields/field";
import {FormCompiler} from "@web/views/form/form_compiler";
import {InnerGroup, OuterGroup} from "@web/views/form/form_group/form_group";
import {FormLabel} from "@web/views/form/form_label";
import {ViewButton} from "@web/views/view_button/view_button";
import {toStringExpression} from "@web/views/utils";

patch(Field.prototype, {
    setup() {
        super.setup(...arguments);
        this.customization = useService("escodoo_customization");
    },
    get classNames() {
        const names = super.classNames;
        if (
            this.customization?.state.enabled &&
            (isFormRootField(this) || isKanbanRoot(this))
        ) {
            names.o_esc_customization_target = true;
        }
        return names;
    },
    onCustomizationClick(ev) {
        openCustomizationFor(this, this.props.name, ev);
    },
});

patch(FormLabel.prototype, {
    setup() {
        super.setup?.(...arguments);
        this.customization = useService("escodoo_customization");
    },
    get className() {
        const names = super.className;
        if (this.customization?.state.enabled && isFormRootField(this)) {
            return `${names} o_esc_customization_target`.trim();
        }
        return names;
    },
    onCustomizationClick(ev) {
        openCustomizationFor(this, this.props.fieldName, ev);
    },
});

patch(Notebook.prototype, {
    setup() {
        super.setup(...arguments);
        this.customization = useService("escodoo_customization");
    },
    get navItems() {
        const items = super.navItems;
        if (!(this.customization?.state.enabled && isFormRootField(this))) {
            return items;
        }
        return items.map(([id, page]) => {
            if (!(page.name || page.title)) {
                return [id, page];
            }
            const className =
                `${page.className || ""} o_esc_customization_target`.trim();
            return [id, {...page, className}];
        });
    },
    onCustomizationNavClick(ev, navItem) {
        this.activatePage(navItem[0]);
        const name = navItem[1].name;
        const title = navItem[1].title || "";
        if (!(name || title)) {
            return;
        }
        openCustomizationFor(this, name || title, ev, {
            anchorKind: "page",
            fieldLabel: title || name,
            anchorString: name ? "" : title,
        });
    },
});

patch(ViewButton.prototype, {
    setup() {
        super.setup(...arguments);
        this.customization = useService("escodoo_customization");
    },
    getClassName() {
        const names = super.getClassName();
        const name = this.clickParams?.name;
        if (name && this.customization?.state.enabled && isFormRootField(this)) {
            return `${names} o_esc_customization_target`.trim();
        }
        return names;
    },
    onClick(ev) {
        const name = this.clickParams?.name;
        if (
            name &&
            openCustomizationFor(this, String(name), ev, {
                anchorKind: "button",
                fieldLabel: this.props.string || String(name),
            })
        ) {
            return;
        }
        return super.onClick(ev);
    },
});

patch(FormCompiler.prototype, {
    compileGroup(el, params) {
        const formGroup = super.compileGroup(el, params);
        if (!formGroup) {
            return formGroup;
        }
        formGroup.setAttribute(
            "groupName",
            toStringExpression(el.getAttribute("name") || "")
        );
        formGroup.setAttribute(
            "groupTitle",
            toStringExpression(el.getAttribute("string") || "")
        );
        return formGroup;
    },
});

function patchFormGroup(GroupClass) {
    const baseProps = GroupClass.props;
    GroupClass.props = [...baseProps, "groupName?", "groupTitle?"];
    patch(GroupClass.prototype, {
        setup() {
            super.setup?.(...arguments);
            this.customization = useService("escodoo_customization");
        },
        get customizationTargetClass() {
            if (
                !(
                    this.customization?.state.enabled &&
                    isFormRootField(this) &&
                    (this.props.groupName || this.props.groupTitle)
                )
            ) {
                return "";
            }
            return "o_esc_customization_target";
        },
        onCustomizationClick(ev) {
            const name = this.props.groupName || "";
            const title = this.props.groupTitle || "";
            if (!(name || title)) {
                return;
            }
            openCustomizationFor(this, name || title, ev, {
                anchorKind: "group",
                fieldLabel: title || name,
                anchorString: name ? "" : title,
            });
        },
    });
}

patchFormGroup(InnerGroup);
patchFormGroup(OuterGroup);
