/** @odoo-module **/


import { FormController } from "@web/views/form/form_controller";
import { formView }       from "@web/views/form/form_view";
import { registry }       from "@web/core/registry";
import { useEffect }      from "@odoo/owl";

class BoqFormController extends FormController {
    setup() {
        super.setup();

        useEffect(
            () => { this._deduplicateTradeVendors(); },
            () => {
                try {
                    return [this.model.root.data.trade_vendor_ids.records.length];
                } catch (_) {
                    return [0];
                }
            }
        );
    }

    _deduplicateTradeVendors() {
        try {
            const record = this.model && this.model.root;
            if (!record || !record.data) return;

            const list = record.data.trade_vendor_ids;
            if (!list || !list.records || list.records.length < 2) return;

            const seen = new Set();
            for (const sub of [...list.records]) {
                const cat    = sub.data && sub.data.category_id;
                const catId  = Array.isArray(cat)             ? cat[0]
                             : (cat && typeof cat === "object") ? (cat.id ?? cat[0])
                             : cat;
                if (!catId) continue;

                if (seen.has(catId)) {
                    try { list.delete(sub); }
                    catch (_) {
                        try { sub.delete(); }
                        catch (_2) {  }
                    }
                } else {
                    seen.add(catId);
                }
            }
        } catch (_) {
        }
    }
}

const boqFormView = { ...formView, Controller: BoqFormController };
registry.category("views").add("boq_form", boqFormView);
