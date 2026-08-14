import {useEffect} from "@odoo/owl";
import {patch} from "@web/core/utils/patch";
import {NavBar} from "@web/webclient/navbar/navbar";
import {useCustomizationService} from "./customization_service";

patch(NavBar.prototype, {
    setup() {
        super.setup(...arguments);
        this.customization = useCustomizationService();
        useEffect(
            () => {
                const el = this.root.el;
                if (!el) {
                    return;
                }
                const onClick = (ev) => this.onCustomizationNavClick(ev);
                el.addEventListener("click", onClick, true);
                return () => el.removeEventListener("click", onClick, true);
            },
            () => [this.root.el]
        );
    },
    onCustomizationNavClick(ev) {
        if (!this.customization?.state.enabled) {
            return;
        }
        const node = ev.target.closest("[data-menu-xmlid]");
        if (!node) {
            return;
        }
        const xmlid = node.getAttribute("data-menu-xmlid");
        if (!xmlid) {
            return;
        }
        const menu = this.menuService.getAll().find((item) => item.xmlid === xmlid);
        if (!this.openMenuCustomization(menu)) {
            return;
        }
        ev.preventDefault();
        ev.stopPropagation();
        ev.stopImmediatePropagation();
    },
    openMenuCustomization(menu) {
        if (!this.customization?.state.enabled || !menu?.xmlid) {
            return false;
        }
        this.customization.openFieldDialog({
            fieldName: menu.xmlid,
            fieldLabel: menu.name,
            model: "ir.ui.menu",
            viewType: "menu",
            anchorKind: "menu",
            menuId: menu.id,
        });
        return true;
    },
    onNavBarDropdownItemSelection(menu) {
        if (this.openMenuCustomization(menu)) {
            return;
        }
        return super.onNavBarDropdownItemSelection(menu);
    },
    async _onMenuClicked(menu) {
        if (this.openMenuCustomization(menu)) {
            return;
        }
        return super._onMenuClicked(menu);
    },
});
