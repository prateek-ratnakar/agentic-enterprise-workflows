"""Generate the synthetic case sets. Seeded, so every run is reproducible.

Realism choices: most cases state their reason clearly, some mix signals from
two categories, some are vague, some are missing evidence, and a few carry
account flags or high amounts. Ground truth is written to each case under
"truth" and is hidden from the agents by the pipeline.
"""
import json
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
WF = os.path.join(HERE, "..", "workflows")

TEXT = {
 "o2c_deductions": {
  "pricing_discrepancy": ["Short-paid invoice {inv}: unit cost billed above the rate agreed in our contract.",
                          "Deducting the cost difference on {inv}, you overcharged versus contract pricing.",
                          "Pricing on {inv} does not match the price list we signed, deduction taken."],
  "promotion_allowance": ["Deduction on {inv} for the spring promotion display allowance.",
                          "Trade allowance for feature ad week 14 taken against {inv}.",
                          "Scan-back promo funds deducted from {inv} as agreed with your rep."],
  "shortage": ["Received less than invoiced on {inv}, 4 missing cases.",
               "Shortage on delivery for {inv}, fewer units than the packing list.",
               "Short shipment against {inv}, deducting the missing quantity."],
  "damaged_goods": ["{inv}: 12 units arrived crushed and leaking, deducting damaged goods.",
                    "Damaged pallet on {inv}, broken cartons, photos attached.",
                    "Spoiled product received on {inv}, deduction for damage."],
  "compliance_chargeback": ["Compliance fine on {inv}: ASN sent after the truck arrived.",
                            "Chargeback for late delivery outside appointment window, {inv}.",
                            "Labeling violation per routing guide on {inv}, chargeback applied."]},
 "bfsi_collections": {
  "promise_to_pay": ["I will pay on the 5th when salary comes in.", "Promise to pay the full EMI next week.",
                     "Can pay by friday, please stop calling till then."],
  "already_paid": ["I already paid yesterday through UPI, transaction id attached.",
                   "Paid the EMI, here is the UTR and receipt.", "This is already paid, check your records."],
  "charge_dispute": ["Why is there a late fee when I paid on the due date? I dispute this charge.",
                     "Bounce charge applied twice, wrong amount on statement.", "Penalty charge looks incorrect, please check."],
  "hardship": ["I lost my job last month and cannot pay right now.", "My father is in hospital, medical expenses, I cannot pay this month.",
               "Facing hardship after job loss, need time."],
  "wrong_party": ["Wrong number, this is not my loan.", "I do not know this person, who is this?", "I am not the borrower, stop calling."]},
 "s2p_invoice_exceptions": {
  "price_variance": ["Invoice {inv} unit price higher than PO, price variance flagged.",
                     "Price mismatch between PO and invoice {inv}, rate difference of 1.5 percent.",
                     "Supplier priced higher than PO on {inv}."],
  "quantity_variance": ["Invoice {inv} quantity does not match GRN, partial delivery.",
                        "Goods receipt shows fewer units received than invoice {inv}.",
                        "Qty billed on {inv} exceeds goods receipt."],
  "missing_po": ["Invoice {inv} received with no PO reference, PO not found.",
                 "Service invoice {inv} raised without purchase order.", "Missing PO on {inv}, no purchase order in system."],
  "duplicate_invoice": ["Possible duplicate: {inv} looks like the same invoice paid last month.",
                        "Supplier resubmitted {inv}, copy of invoice already invoiced?", "Duplicate flag on {inv}."],
  "tax_mismatch": ["GST rate on {inv} differs from item master.", "Tax code HSN mismatch on invoice {inv}.",
                   "VAT on {inv} does not match vendor master tax rate."]},
}
VAGUE = {"o2c_deductions": ["Deduction taken on {inv}, see remittance.", "Short pay on {inv}, reason to follow."],
         "bfsi_collections": ["Call me later.", "Ok noted."],
         "s2p_invoice_exceptions": ["Match exception on {inv}, please review.", "Invoice {inv} blocked in workflow."]}
FLAGS = {"o2c_deductions": ["key_account", "legal_hold"],
         "bfsi_collections": ["vulnerable_customer", "complaint_escalated", "legal_notice_issued"],
         "s2p_invoice_exceptions": ["new_supplier_first_invoice", "sanctions_screening_hit"]}
AMOUNT = {"o2c_deductions": (150, 9000), "bfsi_collections": (4000, 80000), "s2p_invoice_exceptions": (300, 18000)}


def generate(workflow_id, n=40, seed=7):
    rng = random.Random(seed)
    cfg = json.load(open(os.path.join(WF, workflow_id, "config.json")))
    cats = list(cfg["categories"].keys())
    all_attrs = sorted(set(a for c in cfg["categories"].values() for a in c["valid_if"]))
    cases = []
    for i in range(n):
        true_cat = cats[i % len(cats)]
        inv = "INV-%05d" % rng.randint(10000, 99999)
        roll = rng.random()
        if roll < 0.78:
            text = rng.choice(TEXT[workflow_id][true_cat])
        elif roll < 0.90:
            other = rng.choice([c for c in cats if c != true_cat])
            text = rng.choice(TEXT[workflow_id][other]) + " " + rng.choice(TEXT[workflow_id][true_cat])
        else:
            text = rng.choice(VAGUE[workflow_id])
        text = text.format(inv=inv)
        attrs = dict((a, rng.random() < 0.6) for a in all_attrs)
        outcome = "valid" if rng.random() < 0.62 else "invalid"
        for a in cfg["categories"][true_cat]["valid_if"]:
            attrs[a] = True
        if outcome == "invalid":
            attrs[rng.choice(cfg["categories"][true_cat]["valid_if"])] = False
        info_missing = rng.random() < 0.1
        if info_missing:
            attrs[rng.choice(cfg["categories"][true_cat]["valid_if"])] = None
        lo, hi = AMOUNT[workflow_id]
        amount = round(rng.uniform(lo, hi), 2) if rng.random() < 0.85 else round(rng.uniform(hi, hi * 2.5), 2)
        flags = [rng.choice(FLAGS[workflow_id])] if rng.random() < 0.08 else []
        cases.append({"id": "%s-%03d" % (workflow_id.split("_")[0].upper(), i + 1), "amount": amount,
                      "text": text, "attributes": attrs, "flags": flags,
                      "truth": {"category": true_cat, "outcome": outcome, "info_missing": info_missing}})
    return cases


if __name__ == "__main__":
    for wf in TEXT:
        cases = generate(wf)
        with open(os.path.join(WF, wf, "cases.json"), "w") as fh:
            json.dump(cases, fh, indent=1)
            fh.write("\n")
        print(wf, len(cases), "cases")
