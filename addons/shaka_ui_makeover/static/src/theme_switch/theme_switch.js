/**
 * ShakaERP Liquid Glass - Theme Switch Service
 * Toggles data-theme="glass" on <html> root; persists choice in cookie.
 * Default: glass ON. When skeuomorphic is uninstalled, this becomes the only theme.
 */
odoo.define('shaka_ui_makeover.ThemeSwitch', function (require) {
    'use strict';

    const cookie = require('web.cookie');
    const SystrayMenu = require('web.SystrayMenu');
    const Widget = require('web.Widget');

    const THEME_KEY = 'shaka_theme';
    const DEFAULT_THEME = 'glass';

    function applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        cookie.set(THEME_KEY, theme, { expires: 365 });
    }

    function getTheme() {
        return cookie.get(THEME_KEY) || DEFAULT_THEME;
    }

    // Apply on first load (before any UI is rendered)
    applyTheme(getTheme());

    const ThemeSwitchItem = Widget.extend({
        template: 'shaka_ui_makeover.ThemeSwitchItem',
        events: {
            'click .o_theme_switch_button': '_onToggle',
        },

        init: function () {
            this._super.apply(this, arguments);
            this.currentTheme = getTheme();
        },

        _onToggle: function (ev) {
            ev.preventDefault();
            ev.stopPropagation();
            const newTheme = this.currentTheme === 'glass' ? 'skeuomorphic' : 'glass';
            this.currentTheme = newTheme;
            applyTheme(newTheme);
            this.$('.o_theme_switch_button span').text(newTheme === 'glass' ? 'Glass' : 'Skeuomorphic');
            // Update checkbox state
            this.$('.o_theme_switch_button input').prop('checked', newTheme === 'glass');
        },

        willStart: function () {
            return this._super.apply(this, arguments).then(() => {
                // Initial render sync
                this.$('.o_theme_switch_button span').text(this.currentTheme === 'glass' ? 'Glass' : 'Skeuomorphic');
                this.$('.o_theme_switch_button input').prop('checked', this.currentTheme === 'glass');
            });
        },
    });

    // Register in the systray (user menu)
    SystrayMenu.Items.push(ThemeSwitchItem);

    return {
        applyTheme,
        getTheme,
    };
});