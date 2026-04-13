/** @odoo-module **/
/**
 * BOQ Form — client-side deduplication of trade_vendor_ids.
 *
 * Root cause of duplication:
 *   @api.onchange('category_ids') fires multiple concurrent RPC calls when
 *   categories are added quickly via the many2many_tags widget.  Odoo's
 *   onchange protocol applies responses ADDITIVELY on the client (no
 *   clear-all command in the diff), so every concurrent call that saw an
 *   empty trade_vendor_ids appends a full new set of rows — producing
 *   duplicates like [Electrical, Civil, Electrical].
 *
 * Fix (client layer):
 *   Register a custom FormController via js_class="boq_form".  OWL's
 *   useEffect watches trade_vendor_ids.records.length and immediately
 *   removes any rows whose category_id already appeared earlier in the
 *   list.  The effect runs synchronously after each re-render, so
 *   duplicates are removed before the user has a chance to see them.
 *
 * Fix (server layer — see boq_boq.py):
 *   _dedup_trade_vendor_cmds() in create() / write() ensures the database
 *   is always clean even if a duplicate somehow survives to save time.
 */

import { FormController } from "@web/views/form/form_controller";
import { formView }       from "@web/views/form/form_view";
import { registry }       from "@web/core/registry";
import { useEffect }      from "@odoo/owl";

class BoqFormController extends FormController {
    setup() {
        super.setup();

        // Re-run dedup whenever the number of trade_vendor_ids rows changes
        // (additions trigger dedup; after dedup the count stabilises).
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

    /**
     * Remove duplicate trade_vendor rows that share the same category_id.
     * Keeps the FIRST occurrence and deletes subsequent ones.
     * All errors are swallowed — deduplication is best-effort and must
     * never crash the form.
     */
    _deduplicateTradeVendors() {
        try {
            const record = this.model && this.model.root;
            if (!record || !record.data) return;

            const list = record.data.trade_vendor_ids;
            if (!list || !list.records || list.records.length < 2) return;

            const seen = new Set();
            for (const sub of [...list.records]) {
                // Many2one value can be [id, display_name] or { id, ... }
                const cat    = sub.data && sub.data.category_id;
                const catId  = Array.isArray(cat)             ? cat[0]
                             : (cat && typeof cat === "object") ? (cat.id ?? cat[0])
                             : cat;
                if (!catId) continue;

                if (seen.has(catId)) {
                    // Duplicate row — remove it from the list
                    try { list.delete(sub); }
                    catch (_) {
                        try { sub.delete(); }
                        catch (_2) { /* ignore — can't delete this row */ }
                    }
                } else {
                    seen.add(catId);
                }
            }
        } catch (_) {
            // Never crash the form over a dedup failure
        }
    }
}

const boqFormView = { ...formView, Controller: BoqFormController };
registry.category("views").add("boq_form", boqFormView);
