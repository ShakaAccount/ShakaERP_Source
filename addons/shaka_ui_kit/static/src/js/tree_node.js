/** @odoo-module **/
import {Component, useRef, onMounted, onPatched, onWillUnmount} from "@odoo/owl";

const STAGGER_CAP_NODES = 25;

export class TreeNode extends Component {
    setup() {
        this.sentinelRef = useRef("sentinel");
        this._sentinelEl = null;

        this._syncSentinel = () => {
            const el = this.sentinelRef.el;
            if (el === this._sentinelEl) return;
            if (this._sentinelEl && this.props.unregisterSentinel) {
                this.props.unregisterSentinel(this._sentinelEl);
            }
            this._sentinelEl = el || null;
            if (el && this.props.registerSentinel) {
                this.props.registerSentinel(el, this.props.node);
            }
        };

        if (this.props.registerSentinel) {
            onMounted(this._syncSentinel);
            onPatched(this._syncSentinel);
            onWillUnmount(() => {
                if (this._sentinelEl && this.props.unregisterSentinel) {
                    this.props.unregisterSentinel(this._sentinelEl);
                    this._sentinelEl = null;
                }
            });
        }

        if (this.props.showCheckbox) {
            this.checkboxRef = useRef("checkbox");
            const syncIndeterminate = () => {
                const el = this.checkboxRef.el;
                if (el) {
                    el.indeterminate = this.checkState === "partial";
                }
            };
            onMounted(syncIndeterminate);
            onPatched(syncIndeterminate);
        }
    }

    get hasChildren() {
        return !!(this.props.children && this.props.children.length);
    }

    get isSelected() {
        return this.props.selectedId === this.props.node.id;
    }

    get isOpen() {
        return !!this.props.expandedIds[this.props.node.id];
    }

    get hasMoreChildren() {
        return this.props.childHasMore ? this.props.childHasMore(this.props.node) : false;
    }

    get checkState() {
        return this.props.checkState ? this.props.checkState(this.props.node) : "unchecked";
    }

    get staggerStyle() {
        const idx = this.props.index || 0;
        const delay = idx >= STAGGER_CAP_NODES ? 0 : Math.min(idx * 22, 260);
        return `--stagger: ${delay}ms; padding-inline-start: ${this.props.level * 14 + 8}px`;
    }

    onClick(ev) {
        if (this.props.onSelect) {
            ev.stopPropagation();
            this.props.onSelect(this.props.node);
        }
    }

    onToggle(ev) {
        ev.stopPropagation();
        if (this.hasChildren) {
            this.props.onToggle(this.props.node.id);
        }
    }

    onCheckChange(ev) {
        this.props.onCheck(this.props.node, ev.target.checked);
    }
}

TreeNode.template = "shaka_ui_kit.TreeNode";
TreeNode.props = {
    node: Object,
    children: {type: Array, optional: true},
    level: Number,
    index: {type: Number, optional: true},
    selectedId: {type: [Number, String], optional: true},
    expandedIds: Object,
    closingIds: Object,
    onToggle: Function,
    onSelect: {type: Function, optional: true},
    disabled: {type: Boolean, optional: true},
    showCheckbox: {type: Boolean, optional: true},
    checkState: {type: Function, optional: true},
    onCheck: {type: Function, optional: true},
    getChildren: {type: Function, optional: true},
    childTotal: {type: Function, optional: true},
    childShown: {type: Function, optional: true},
    childHasMore: {type: Function, optional: true},
    registerSentinel: {type: Function, optional: true},
    unregisterSentinel: {type: Function, optional: true},
    slots: {type: Object, optional: true},
};
TreeNode.components = {TreeNode};
