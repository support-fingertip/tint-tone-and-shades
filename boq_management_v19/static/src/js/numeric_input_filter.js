/**
 * Block non-numeric characters in Float / Monetary / Integer / Percentage
 * field inputs across the backend (BOQ qty/unit_price, RFQ/PO product_qty,
 * price_unit, taxes, etc.).
 *
 * Uses 'beforeinput' so we reject the keystroke (and pasted text) before it
 * reaches the OWL widget — the field never sees an alphabet.
 *
 * Allowed characters: digits, '.', ',', '-' (for negatives) and control keys
 * (backspace/arrows/etc. arrive with ev.data === null and are passed through).
 */
const NUMERIC_FIELD_SELECTOR =
    ".o_field_widget.o_field_float, " +
    ".o_field_widget.o_field_monetary, " +
    ".o_field_widget.o_field_integer, " +
    ".o_field_widget.o_field_percentage";

const ALLOWED_CHARS = /^[0-9.,\-]+$/;

document.addEventListener(
    "beforeinput",
    (ev) => {
        const input = ev.target;
        if (!(input instanceof HTMLInputElement)) {
            return;
        }
        const widget = input.closest(NUMERIC_FIELD_SELECTOR);
        if (!widget) {
            return;
        }
        if (ev.data == null) {
            return;
        }
        if (!ALLOWED_CHARS.test(ev.data)) {
            ev.preventDefault();
        }
    },
    true,
);
