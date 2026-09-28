import { fields } from "@mail/core/common/record";
import { DiscussApp } from "@mail/core/public_web/discuss_app_model";
import { Thread } from "@mail/core/common/thread_model";

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

patch(DiscussApp.prototype, {
    setup(env) {
        super.setup(...arguments);
        this.telegram = fields.One("DiscussAppCategory", {
            compute() {
                return {
                    addTitle: _t("Search Telegram Chat"),
                    extraClass: "o-mail-DiscussSidebarCategory-telegram",
                    hideWhenEmpty: true,
                    icon: "fa fa-telegram",
                    id: "telegram",
                    name: _t("Telegram"),
                    sequence: 21,
                    serverStateKey: "is_discuss_sidebar_category_telegram_open",
                };
            },
            eager: true,
        });
    },
});

patch(Thread.prototype, {
    _computeDiscussAppCategory() {
        return this.channel_type === "telegram"
            ? this.store.discuss.telegram
            : super._computeDiscussAppCategory();
    },
});
