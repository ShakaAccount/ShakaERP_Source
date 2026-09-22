/** @odoo-module **/

// Odoo stores the user's display preference in the `color_scheme` cookie.
// Expose it as a stable DOM class so the Shaka theme can style the selected
// mode explicitly; relying only on prefers-color-scheme misses Odoo's own
// Dark/Light selector.
function syncShakaThemeMode() {
    const colorSchemeCookie = document.cookie
        .split(";")
        .map((item) => item.trim().split("="))
        .find(([key]) => key === "color_scheme");
    const explicitScheme = colorSchemeCookie && colorSchemeCookie[1];
    const systemDark = window.matchMedia
        && window.matchMedia("(prefers-color-scheme: dark)").matches;
    const dark = explicitScheme === "dark"
        || (explicitScheme !== "light" && systemDark);
    document.documentElement.classList.toggle("shaka-dark-mode", dark);
}

syncShakaThemeMode();
window.addEventListener("pageshow", syncShakaThemeMode);
if (window.matchMedia) {
    window.matchMedia("(prefers-color-scheme: dark)")
        .addEventListener("change", syncShakaThemeMode);
}
