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
                    this.state.selectedReport = reports[0];
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

    selectReport(report) {
        this.state.selectedReport = report;
    }
}

PowerBIPortal.template = "powerbi_portal.Portal";
PowerBIPortal.components = { TreeNode: PowerBITreeNode };

registry.category("actions").add("powerbi_portal.portal", PowerBIPortal);
