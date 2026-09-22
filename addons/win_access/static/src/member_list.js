import { Component, onWillStart, useState } from "@odoo/owl";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

const SOURCES = { ad: ["ad", "odoo"], local: ["local"] };

/** Group members as cards. AD users must be picked from the list; local users are picked or typed. */
export class MemberListField extends Component {
    static template = "win_access.MemberList";
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.state = useState({ users: [] });
        onWillStart(async () => {
            this.state.users = await this.orm.searchRead(
                "win.access.option", [["kind", "=", "user"]], ["name", "source", "display_name", "upn"],
                { order: "name" });
        });
    }

    get list() {
        return this.props.record.data[this.props.name];
    }

    choices(kind) {
        return this.state.users.filter((u) => SOURCES[kind].includes(u.source));
    }

    label(u) {
        return [u.display_name, u.upn].filter(Boolean).join(" — ");
    }

    // AD rows must match the list; local rows may be a new account
    isUnknownAd(rec) {
        return rec.data.kind === "ad" && rec.data.name && !rec.data.user_option_id;
    }

    isNewLocal(rec) {
        return rec.data.kind === "local" && rec.data.name && !rec.data.user_option_id;
    }

    setKind(rec, kind) {
        if (rec.data.kind !== kind) {
            rec.update({ kind, user_option_id: false, name: "" });
        }
    }

    setName(rec, value) {
        const v = value.trim();
        const hit = this.choices(rec.data.kind).find((u) => u.name.toLowerCase() === v.toLowerCase());
        rec.update(hit
            ? { user_option_id: { id: hit.id, display_name: hit.name }, name: hit.name }
            : { user_option_id: false, name: v });
    }

    async add() {
        await this.list.addNewRecord({ position: "bottom" });
    }

    remove(rec) {
        if (rec.data.state !== "added") {
            return this.list.delete(rec);
        }
        this.dialog.add(ConfirmationDialog, {
            title: "Remove member",
            body: `Removing "${rec.data.name}" also takes the account out of the Windows group when you save.`,
            confirmLabel: "Remove",
            confirm: () => this.list.delete(rec),
            cancel: () => {},
        });
    }
}

registry.category("fields").add("win_access_members", {
    component: MemberListField,
    supportedTypes: ["one2many"],
});
