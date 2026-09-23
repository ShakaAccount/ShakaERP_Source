/** @odoo-module **/
import { onMounted, onWillUnmount } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { patch } from "@web/core/utils/patch";

const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

// Card resize on every dialog: when the content changes size, pin the old
// height, then set the new one so `.t-resize` tweens it; release to `auto`
// once done so the dialog keeps sizing naturally.
patch(Dialog.prototype, {
    setup() {
        super.setup();
        let observer;
        onMounted(() => {
            const card = this.modalRef.el?.querySelector(".modal-content");
            if (!card || this.env.isSmall) {
                return; // fullscreen dialogs on mobile: nothing to resize
            }
            card.classList.add("t-resize");
            let last = card.offsetHeight;
            let resizing = false;
            const release = (ev) => {
                if (ev.target === card && ev.propertyName === "height") {
                    card.style.height = "";
                    card.classList.remove("is-resizing");
                    resizing = false; // the observer re-checks the natural height
                }
            };
            card.addEventListener("transitionend", release);
            card.addEventListener("transitioncancel", release);
            observer = new ResizeObserver(() => {
                const next = card.offsetHeight;
                if (resizing || next === last) {
                    return;
                }
                if (reducedMotion.matches) {
                    last = next;
                    return;
                }
                resizing = true;
                card.classList.add("is-resizing");
                card.style.height = `${last}px`;
                void card.offsetHeight; // commit the old height before tweening
                card.style.height = `${next}px`;
                last = next;
            });
            observer.observe(card);
        });
        onWillUnmount(() => observer?.disconnect());
    },
});
