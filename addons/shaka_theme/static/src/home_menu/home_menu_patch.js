import { useState } from "@odoo/owl";
import { user } from "@web/core/user";
import { patch } from "@web/core/utils/patch";
import { HomeMenu } from "@web_enterprise/webclient/home_menu/home_menu";

// Free-placement app grid. `homemenu_config` stays a flat xmlid array, read
// row-major in COLS columns; `null` is an empty cell. Stock `reorderApps()`
// only uses indexOf(xmlid), so it still works on this shape.
const COLS = 6;

patch(HomeMenu.prototype, {
    setup() {
        super.setup();
        const saved = JSON.parse(user.settings?.homemenu_config || "null");
        this.grid = useState({
            layout: Array.isArray(saved) ? saved : [],
            dragged: null,
        });
    },

    /** Apps (or null for gaps) in cell order. Small screens: packed. */
    get cells() {
        const apps = this.displayedApps;
        if (this.env.isSmall) {
            return apps;
        }
        const byXmlid = Object.fromEntries(apps.map((app) => [app.xmlid, app]));
        const cells = this.grid.layout.map((xmlid) => byXmlid[xmlid] || null);
        // Apps never placed (new install, new access) take the first free cell.
        for (const app of apps) {
            if (!cells.includes(app)) {
                const free = cells.indexOf(null);
                free === -1 ? cells.push(app) : (cells[free] = app);
            }
        }
        while (cells.length % COLS) {
            cells.push(null);
        }
        if (this.grid.dragged) {
            // A spare row so an app can be dropped below everything else.
            cells.push(...Array(COLS).fill(null));
        }
        return cells;
    },

    _enableAppsSorting() {
        return false;
    },

    _onCellDragStart(ev, app) {
        if (!app || this.env.isSmall) {
            ev.preventDefault();
            return;
        }
        ev.dataTransfer.effectAllowed = "move";
        ev.dataTransfer.setData("text/plain", app.xmlid);
        this.grid.dragged = app.xmlid;
    },

    _onCellDragEnd() {
        this.grid.dragged = null;
    },

    /** Close every gap, keeping the current reading order. */
    _onAutoArrange() {
        this._saveLayout(this.cells.filter(Boolean).map((app) => app.xmlid));
    },

    _onCellDrop(index) {
        const cells = this.cells.map((app) => app?.xmlid || null);
        const from = cells.indexOf(this.grid.dragged);
        this.grid.dragged = null;
        if (from === -1 || from === index) {
            return;
        }
        // Swap: onto an empty cell it's a move, onto an app they trade places.
        [cells[from], cells[index]] = [cells[index], cells[from]];
        while (cells.length && cells.at(-1) === null) {
            cells.pop();
        }
        this._saveLayout(cells);
    },

    _saveLayout(cells) {
        this.grid.layout = cells;
        this.props.reorderApps(cells.filter(Boolean));
        user.setUserSettings("homemenu_config", JSON.stringify(cells));
    },

    /** Arrow keys walk the grid by cell, skipping gaps (wraps around). */
    _updateFocusedIndex(cmd) {
        const step = { nextLine: COLS, previousLine: -COLS, nextColumn: 1, previousColumn: -1 }[cmd];
        if (!step || this.env.isSmall || this.state.focusedIndex === null) {
            return super._updateFocusedIndex(cmd);
        }
        const apps = this.displayedApps;
        const cells = this.cells;
        let i = cells.indexOf(apps[this.state.focusedIndex]);
        for (let n = 0; n < cells.length; n++) {
            i = (i + step + cells.length) % cells.length;
            if (cells[i]) {
                this.state.focusedIndex = apps.indexOf(cells[i]);
                return;
            }
        }
    },
});
