/** @odoo-module **/
import { onWillPatch, onWillUnmount, useEffect } from "@odoo/owl";
import { AutoComplete } from "@web/core/autocomplete/autocomplete";
import { patch } from "@web/core/utils/patch";
import { closeMenu, openMenu } from "./morph";

// Dropdown menu morph on AutoComplete menus (many2one and other search-as-you-
// type fields). They aren't Popovers: the menu is a t-if'd <ul> inside the
// component, so open on mount and play the close just before it's patched out.
patch(AutoComplete.prototype, {
    setup() {
        super.setup();
        if (!this.props.dropdown) {
            return; // inline option list, not a floating menu
        }
        let shown = null;
        // Declared after usePosition's effect, so the menu is already placed.
        useEffect(() => {
            const menu = this.listRef.el;
            if (menu && menu !== shown) {
                openMenu(menu, this.inputRef.el, "t-morph");
            }
            shown = menu;
        });
        onWillPatch(() => {
            if (this.listRef.el && !this.displayOptions) {
                closeMenu(this.listRef.el, this.inputRef.el);
            }
        });
        onWillUnmount(() => closeMenu(this.listRef.el, this.inputRef.el));
    },
});
