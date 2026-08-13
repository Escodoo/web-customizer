import {isFormRootField, openCustomizationFor} from "./customization_service";
import {Notebook} from "@web/core/notebook/notebook";
import {useService} from "@web/core/utils/hooks";
import {patch} from "@web/core/utils/patch";
import {Field} from "@web/views/fields/field";
import {FormLabel} from "@web/views/form/form_label";
import {ViewButton} from "@web/views/view_button/view_button";

patch(Field.prototype, {
    setup() {
        super.setup(...arguments);
        this.customization = useService("escodoo_customization");
    },
    get classNames() {
        const names = super.classNames;
        if (this.customization?.state.enabled && isFormRootField(this)) {
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
            if (!page.name) {
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
        if (!name) {
            return;
        }
        openCustomizationFor(this, name, ev, {
            anchorKind: "page",
            fieldLabel: navItem[1].title || name,
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
