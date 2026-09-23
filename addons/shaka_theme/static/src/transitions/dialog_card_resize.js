/** @odoo-module **/
import { onMounted, onWillUnmount } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { patch } from "@web/core/utils/patch";

const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
const token = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

// Card resize on every dialog: when the content changes size, tween the card's
// height from its old to its new natural height (Web Animations, so the height
// stays `auto` underneath and the dialog keeps sizing naturally).
// Interruptible: content that changes again mid-tween retargets from the
// height currently on screen instead of waiting for the tween to end.
patch(Dialog.prototype, {
    setup() {
        super.setup();
        const observers = [];
        onMounted(() => {
            const card = this.modalRef.el?.querySelector(".modal-content");
            if (!card || this.env.isSmall) {
                return; // fullscreen dialogs on mobile: nothing to resize
            }
            card.classList.add("t-resize");
            let last = card.offsetHeight; // natural height the card is heading to
            let anim = null;

            const tween = (from, to) => {
                card.classList.add("is-resizing");
                anim = card.animate(
                    { height: [`${from}px`, `${to}px`] },
                    { duration: parseFloat(token("--resize-dur")) || 300, easing: token("--resize-ease") || "ease-out" }
                );
                anim.onfinish = () => {
                    anim = null;
                    card.classList.remove("is-resizing");
                };
            };

            const retarget = () => {
                if (reducedMotion.matches) {
                    last = card.offsetHeight;
                    return;
                }
                if (!anim) {
                    const next = card.offsetHeight;
                    if (next !== last) {
                        tween(last, next);
                        last = next;
                    }
                    return;
                }
                // Mid-tween: lift the animation to measure the natural height.
                // All synchronous, so the lifted frame is never painted.
                const current = card.getBoundingClientRect().height;
                const time = anim.currentTime;
                anim.cancel();
                const next = card.offsetHeight;
                if (next === last) {
                    anim.currentTime = time; // same target: resume where it was
                    anim.play();
                    return;
                }
                tween(current, next);
                last = next;
            };

            // Size changes while tweening are the tween itself; content
            // changes then arrive as DOM mutations.
            const resize = new ResizeObserver(() => !anim && retarget());
            const mutation = new MutationObserver(() => anim && retarget());
            resize.observe(card);
            mutation.observe(card, { childList: true, subtree: true, characterData: true });
            observers.push(resize, mutation);
        });
        onWillUnmount(() => observers.forEach((o) => o.disconnect()));
    },
});
