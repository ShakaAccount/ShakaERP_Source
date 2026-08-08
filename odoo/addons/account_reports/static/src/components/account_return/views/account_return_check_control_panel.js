import { ControlPanel } from "@web/search/control_panel/control_panel";
import { user } from "@web/core/user";

export class AccountReturnCheckControlPanel extends ControlPanel {
    setup() {
        const context = this.env.searchModel.globalContext || {};
        if (context.embedded_actions_config) {
            // Update the embedded actions config in user settings with the newly created embedded actions config.
            // this is used to make the control panel visible when the user is redirected to the next action,
            // after record is created.
            Object.assign(
                user.settings.embedded_actions_config_ids,
                context.embedded_actions_config
            );
        }
        super.setup();
    }
}
