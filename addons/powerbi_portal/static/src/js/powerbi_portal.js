/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { TreeNode } from "@shaka_ui_kit/js/tree_node";

export class PowerBIPortal extends Component {
    static template = "powerbi_portal.Portal";
    static components = { TreeNode };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            roots: [],           // tree nodes: folders { id: fullPath, label, children } and reports { id, label, report }
            open: {},            // folder id -> true while expanded
            closing: {},         // folder id -> true while its collapse animation runs
            selectedReport: null,
            pendingReport: null, // report selected but iframe held back during auth warm-up
            loading: true,
            error: null,
        });
        this.closeTimers = {};

        onWillStart(async () => {
            try {
                const reports = await this.orm.call("powerbi.report", "get_sidebar_reports", []);
                this.state.roots = this._buildTree(reports);
                // Top-level folders start open so the tree isn't fully collapsed on first load.
                for (const node of this.state.roots) {
                    if (node.children) {
                        this.state.open[node.id] = true;
                    }
                }
                const warmed = new Set();
                for (const r of reports) {
                    const o = r.url && this._reportOrigin(r.url);
                    if (o && !warmed.has(o)) {
                        warmed.add(o);
                        this.warmReportOrigin(r.url);
                    }
                }
                if (reports.length) {
                    this.selectReport(reports[0]);
                }
            } catch {
                this.state.error = _t("Could not load the report list. Please contact your administrator.");
            } finally {
                this.state.loading = false;
            }
        });
    }

    _buildTree(reports) {
        const root = { children: [] };
        const folders = { "": root };
        for (const report of reports) {
            const segments = report.path.split("/").filter(Boolean).slice(0, -1);
            let parent = root;
            let path = "";
            for (const seg of segments) {
                path += "/" + seg;
                if (!folders[path]) {
                    folders[path] = { id: path, label: seg, children: [] };
                    parent.children.push(folders[path]);
                }
                parent = folders[path];
            }
            parent.children.push({ id: report.id, label: report.name, report });
        }
        return root.children;
    }

    // Bound arrows: passed as bare props to TreeNode, which calls them detached from `this`.
    getChildren = (node) => node.children || [];

    onSelect = (node) => {
        if (node.children) {
            this.toggleFolder(node.id);
        } else {
            this.selectReport(node.report);
        }
    };

    toggleFolder = (id) => {
        if (this.state.closing[id]) {
            // Reopened mid-collapse: cancel the unmount, the CSS reverses.
            clearTimeout(this.closeTimers[id]);
            delete this.state.closing[id];
        } else if (!this.state.open[id]) {
            this.state.open[id] = true;
        } else {
            this.state.closing[id] = true;
            this.closeTimers[id] = setTimeout(() => {
                delete this.state.open[id];
                delete this.state.closing[id];
            }, parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--acc-collapse")) || 250);
        }
    };

    _reportOrigin(reportUrl) {
        try {
            return new URL(reportUrl, window.location.href).origin;
        } catch {
            return null;
        }
    }

    /**
     * Pre-authenticate the PBIRS origin before loading a report in the iframe.
     *
     * The problem: Odoo is one origin, the report server is another. When a
     * cross-origin iframe loads the report, the browser runs the Windows
     * auth (Negotiate/NTLM) challenge-response *inside the iframe context*,
     * where third-party cookie/credential rules apply - so it re-prompts for
     * login on every load even though the user already has a valid AD session
     * from logging into Odoo.
     *
     * The classic fix: load an <img> (or any subresource) from the report
     * origin FIRST. A subresource request carries credentials and drives the
     * full 401 -> Negotiate/NTLM -> 200 handshake as a normal same-browsing-
     * session request. Once that succeeds, the browser caches the
     * authenticated connection and the report server's session cookie for
     * that origin, and the iframe's own navigate reuses them - no prompt.
     *
     * Uses `new Image()` rather than fetch(): image loads fire the IWA/SPNEGO
     * exchange and the browser attaches Authorization automatically, which a
     * `no-cors` fetch may not. Fails silently (best-effort); the iframe still
     * attempts the report regardless.
     */
    warmReportOrigin(reportUrl) {
        const origin = this._reportOrigin(reportUrl);
        if (origin) {
            // Any path on the origin works for the handshake; the root is the
            // most reliable target (every IIS site responds to it).
            new Image().src = origin + "/?rs:auth=warmup";
        }
    }

    selectReport(report) {
        // Open the folders above the report so the selection is visible.
        const segments = report.path.split("/").filter(Boolean).slice(0, -1);
        let path = "";
        for (const seg of segments) {
            path += "/" + seg;
            this.state.open[path] = true;
        }
        // Warm the PBIRS origin first (let the browser run the Windows-auth
        // handshake at top level and persist the session cookie), THEN reveal
        // the iframe a beat later so its own navigate reuses that cookie
        // instead of re-challenging. Keeps the previous report (or placeholder)
        // visible during the brief warm-up.
        if (report.url) {
            this.warmReportOrigin(report.url);
            this.state.pendingReport = report;
            setTimeout(() => {
                if (this.state.pendingReport?.id === report.id) {
                    this.state.selectedReport = report;
                    this.state.pendingReport = null;
                }
            }, 600);
        } else {
            this.state.selectedReport = report;
        }
    }

    get selectedId() {
        return (this.state.pendingReport || this.state.selectedReport)?.id;
    }
}

registry.category("actions").add("powerbi_portal.portal", PowerBIPortal);
