/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

/**
 * One level of the report tree. Recurses into itself as a real OWL
 * component (not a t-call template) so each level gets its own isolated
 * rendering scope - avoids a classic QWeb bug where a shared "node"
 * variable set via t-set leaks between recursion levels when using t-call
 * recursion instead of real component instances.
 */
class PowerBITreeNode extends Component {
    toggleFolder(fullPath) {
        this.props.toggleFolder(fullPath);
    }
    isExpanded(fullPath) {
        return this.props.expanded.has(fullPath);
    }
    selectReport(report) {
        this.props.selectReport(report);
    }
    isSelected(report) {
        return this.props.selectedReport && this.props.selectedReport.id === report.id;
    }
}
PowerBITreeNode.template = "powerbi_portal.TreeNode";
PowerBITreeNode.props = ["node", "expanded", "selectedReport", "toggleFolder", "selectReport"];
PowerBITreeNode.components = { TreeNode: PowerBITreeNode };

export class PowerBIPortal extends Component {
    setup() {
        this.orm = useService("orm");
        this.state = useState({
            tree: null,          // { name, fullPath, folders: [...], reports: [...] }
            expanded: new Set(), // set of folder fullPaths currently expanded
            selectedReport: null,
            pendingReport: null, // report selected but iframe held back during auth warm-up
            loading: true,
            error: null,
        });

        this.toggleFolder = this.toggleFolder.bind(this);
        this.selectReport = this.selectReport.bind(this);

        onWillStart(async () => {
            try {
                const reports = await this.orm.call("powerbi.report", "get_sidebar_reports", []);
                this.state.tree = this._buildTree(reports);
                // Expand top-level folders by default so the tree isn't fully collapsed on first load.
                for (const folder of this.state.tree.folders) {
                    this.state.expanded.add(folder.fullPath);
                }
                if (reports.length) {
                    const warmed = new Set();
                    for (const r of reports) {
                        if (r.url) {
                            const o = this._reportOrigin(r.url);
                            if (o && !warmed.has(o)) {
                                warmed.add(o);
                                this.warmReportOrigin(r.url);
                            }
                        }
                    }
                    this.selectReport(reports[0]);
                }
            } catch (e) {
                this.state.error = "Could not load the report list. Please contact your administrator.";
            } finally {
                this.state.loading = false;
            }
        });
    }

    _buildTree(reports) {
        const root = { name: "", fullPath: "", children: new Map(), reports: [] };
        for (const report of reports) {
            const segments = report.path.split("/").filter(Boolean);
            const folderSegments = segments.slice(0, -1); // everything except the report itself
            let node = root;
            let pathSoFar = "";
            for (const seg of folderSegments) {
                pathSoFar += "/" + seg;
                if (!node.children.has(seg)) {
                    node.children.set(seg, {
                        name: seg,
                        fullPath: pathSoFar,
                        children: new Map(),
                        reports: [],
                    });
                }
                node = node.children.get(seg);
            }
            node.reports.push(report);
        }
        return this._finalize(root);
    }

    _finalize(node) {
        return {
            name: node.name,
            fullPath: node.fullPath,
            folders: Array.from(node.children.values()).map((c) => this._finalize(c)),
            reports: node.reports,
        };
    }

    toggleFolder(fullPath) {
        if (this.state.expanded.has(fullPath)) {
            this.state.expanded.delete(fullPath);
        } else {
            this.state.expanded.add(fullPath);
        }
    }

    _reportOrigin(reportUrl) {
        try {
            return new URL(reportUrl, window.location.href).origin;
        } catch (e) {
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
        try {
            const origin = this._reportOrigin(reportUrl);
            if (!origin) {
                return;
            }
            // Any path on the origin works for the handshake; the root is the
            // most reliable target (every IIS site responds to it).
            const img = new Image();
            img.src = origin + "/?rs:auth=warmup";
            // If the handshake 2xx'd, the browser has cached the auth; if it
            // 401s, the image just won't load - either way nothing to handle.
        } catch (e) {
            // ignore malformed URLs / blocked requests
        }
    }

    selectReport(report) {
        // Warm the PBIRS origin first (let the browser run the Windows-auth
        // handshake at top level and persist the session cookie), THEN reveal
        // the iframe a beat later so its own navigate reuses that cookie
        // instead of re-challenging. Keeps the previous report (or placeholder)
        // visible during the brief warm-up.
        if (report && report.url) {
            this.warmReportOrigin(report.url);
            this.state.pendingReport = report;
            setTimeout(() => {
                if (this.state.pendingReport && this.state.pendingReport.id === report.id) {
                    this.state.selectedReport = report;
                    this.state.pendingReport = null;
                }
            }, 600);
        } else {
            this.state.selectedReport = report;
        }
    }
}

PowerBIPortal.template = "powerbi_portal.Portal";
PowerBIPortal.components = { TreeNode: PowerBITreeNode };

registry.category("actions").add("powerbi_portal.portal", PowerBIPortal);
