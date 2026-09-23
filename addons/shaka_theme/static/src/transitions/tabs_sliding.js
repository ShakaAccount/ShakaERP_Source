/** @odoo-module **/
import { useEffect, useRef } from "@odoo/owl";
import { Notebook } from "@web/core/notebook/notebook";
import { patch } from "@web/core/utils/patch";

// Tabs sliding: move the pill onto the active tab. Animated on tab switch;
// snapped (no transition) on first paint and whenever the tab list resizes.
patch(Notebook.prototype, {
    setup() {
        super.setup();
        const pillRef = useRef("shakaTabsPill");
        let placed = false;
        const place = (animate) => {
            const pill = pillRef.el;
            const tab = pill?.parentElement.querySelector(":scope > .nav-item > .nav-link.active");
            if (!tab) {
                return false;
            }
            if (!animate) {
                pill.style.transition = "none";
            }
            // Physical left/top on purpose: offsetLeft/Top are physical too,
            // and an inline value can't be flipped by the RTL stylesheet.
            pill.style.left = "0px";
            pill.style.right = "auto";
            pill.style.transform = `translate(${tab.offsetLeft}px, ${tab.offsetTop}px)`;
            pill.style.width = `${tab.offsetWidth}px`;
            pill.style.height = `${tab.offsetHeight}px`;
            if (!animate) {
                void pill.offsetWidth; // commit the snap before restoring the transition
                pill.style.transition = "";
            }
            return true;
        };
        useEffect(
            () => {
                // First successful placement snaps; later tab switches slide.
                placed = place(placed) || placed;
            },
            () => [this.state.currentPage]
        );
        useEffect(
            (list) => {
                if (!list) {
                    return;
                }
                const observer = new ResizeObserver(() => place(false));
                observer.observe(list);
                return () => observer.disconnect();
            },
            () => [pillRef.el?.parentElement]
        );
    },
});
