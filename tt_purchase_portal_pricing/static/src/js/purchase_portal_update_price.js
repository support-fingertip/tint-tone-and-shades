import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

export class PurchasePortalUpdatePrice extends Interaction {
    static selector = ".o_purchase_portal_price_input";

    start() {
        this.el.addEventListener("input", this._onPriceInput.bind(this));
        this.el.addEventListener("change", this._onPriceChange.bind(this));
    }

    _onPriceInput(ev) {
        const input = ev.currentTarget;
        const cleaned = input.value.replace(/[^0-9.]/g, "").replace(/(\..*)\./g, "$1");
        if (input.value !== cleaned) {
            input.value = cleaned;
        }
    }

    _onPriceChange(ev) {
        const input = ev.currentTarget;
        const lineId = input.dataset.lineId;
        const table = input.closest("table");
        const orderId = table.dataset.orderId;
        const token = table.dataset.token;
        const newPrice = parseFloat(input.value) || 0;

        this.waitFor(
            rpc(`/my/purchase/${orderId}/update_line_price`, {
                access_token: token,
                line_id: lineId,
                price_unit: newPrice,
            }).then((result) => {
                if (result.success) {
                    window.location.reload();
                }
            })
        );
    }
}

registry
    .category("public.interactions")
    .add("tt_purchase_portal_pricing.update_price", PurchasePortalUpdatePrice);
