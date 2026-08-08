import { patch } from "@web/core/utils/patch";
import { SampleServer } from "@web/model/sample_server";

/**
 * If `is_timer_running` is set, we see a bunch of running timers
 * which activate TimerHeader and thus when stopping timer in
 * another view makes it through tracebacks
 */
patch(SampleServer.prototype, {
    _generateFieldValue(modelName, fieldName, id) {
        if (fieldName === "is_timer_running") {
            return false;
        }
        return super._generateFieldValue(...arguments);
    },
});
