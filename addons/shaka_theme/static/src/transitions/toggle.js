/** @odoo-module **/

// Toggle (transitions.dev): arm the keyframes in toggle.css on first
// interaction, so switches don't play their "off" animation on load.
document.addEventListener(
    "click",
    (ev) => ev.target.closest?.(".form-switch")?.querySelector(".form-check-input")?.classList.add("is-init"),
    true
);
