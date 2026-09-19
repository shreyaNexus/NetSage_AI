# Responsible AI Log

NetSage AI's job is to accelerate a human's diagnosis, not replace their
judgment. This log records every case where the AI's diagnosis needed to be
corrected by a human reviewer, why it was wrong, and what that tells us
about where the assistant is weak. Full source data: `review/human_review.csv`
(status = `Rejected`) plus a few `Edited` refinements included here for
completeness.

Summary: **6 of 30 cases (20%) were rejected outright**, and a further
6 were accepted-with-edits. All 6 rejections are documented below, as
required (minimum 5).

---

## 1. C003 — VLAN native-mismatch, misread as "trunk not carrying VLAN"

- **AI said:** the trunk's allowed-VLAN list excludes VLAN 20.
- **Actually:** a native VLAN mismatch (VLAN 1 vs VLAN 99) between the two
  switches, explicitly flagged by a CDP warning in the evidence.
- **Why it matters:** the AI reached for the most statistically common
  explanation for "VLAN doesn't cross a trunk" instead of using the specific
  evidence it was given. Confidence was correctly only "medium," which is
  exactly the signal that told the reviewer to double-check before acting.

## 2. C009 — Subnet mask issue, misread as "wrong gateway IP"

- **AI said:** change PC5's gateway address.
- **Actually:** PC5's gateway address is correct; its subnet *mask* is wrong
  (/24 instead of /25), so it treats an off-link router as on-link.
- **Why it matters:** "gateway" was in the topology note, and the AI
  pattern-matched to the more common gateway-address fault instead of
  reading the mask fields closely. The deterministic rule checker
  (`wrong_mask`) caught this independently, showing the value of not relying
  on the AI alone.

## 3. C013 — DHCP default-router misconfig, under-confident non-answer

- **AI said:** low confidence, "review the DHCP pool configuration."
- **Actually:** the evidence directly contained the bad `default-router`
  line (`10.10.80.254` vs the router's real `10.10.80.1`).
- **Why it matters:** this isn't a wrong hypothesis, it's a missed one — the
  AI had enough evidence to commit to "high" confidence and didn't. Vague
  fixes are a failure mode too: they push work back onto the human instead
  of saving them time.

## 4. C019 — OSPF adjacency, misread as "OSPF not enabled"

- **AI said:** OSPF is not configured on the interface.
- **Actually:** OSPF *is* configured; a typo'd subnet mask (/29 vs /30) is
  breaking the adjacency.
- **Why it matters:** an empty `show ip ospf neighbor` table has many
  possible causes, and the AI picked the most common one without checking
  the more specific interface configuration it had already been given.

## 5. C023 — ACL statement order, misread as "missing deny statement"

- **AI said:** add a deny statement for the blocked host.
- **Actually:** the deny statement already exists, but a broader permit
  above it matches first, so the deny is never evaluated.
- **Why it matters:** the proposed fix would have been a no-op (adding a
  rule that already exists further down the list solves nothing). This is a
  comprehension error on ordered, order-sensitive evidence — a category
  worth watching for in future prompt iterations (e.g. asking the AI to
  explicitly restate ACL line order before diagnosing).

## 6. C027 — NAT ACL wildcard, misread as "NAT not configured"

- **AI said:** NAT overload was never turned on.
- **Actually:** NAT overload IS configured; its source ACL uses the wrong
  wildcard mask (`0.0.0.15` instead of `0.0.0.255`), so it only matches 16
  of 254 hosts.
- **Why it matters:** same failure family as C019 — the AI's hypothesis
  contradicted a line that was directly present in the evidence
  (`ip nat inside source list 1 ... overload`), meaning the fix proposed
  would not have changed anything, since NAT was already enabled.

---

## Patterns across all 6 rejections

- **All 6 involve evidence that requires close reading of a specific
  configuration line**, not just recognizing the general symptom category
  (VLAN issue, gateway issue, OSPF issue, ACL issue, NAT issue). The AI
  tends to jump to the most common cause for a symptom category rather than
  verifying against the literal evidence text.
- **3 of 6 (C019, C023, C027) proposed a fix that would have been a no-op**
  because the AI's premise was directly contradicted by evidence already in
  the prompt (OSPF *was* enabled, the deny line *did* exist, NAT *was*
  configured). This is the most operationally dangerous failure mode: a
  confident-sounding fix that changes nothing and wastes a maintenance
  window.
- **Confidence calibration mostly worked**: C003, C019, C023, and C027 came
  back at "medium" or lower-but-still-wrong confidence more often than
  "high," which gave reviewers a signal to double check. C013 is the
  exception — a case where the AI *should* have been confident (the
  evidence was explicit) but under-committed instead.

## Action items for the next prompt iteration

1. Add a rule to `diagnose_prompt.md`: when evidence lists configuration
   *statements* in order (ACL lines, OSPF config, NAT config), explicitly
   instruct the AI to state whether the reported feature is present at all
   before diagnosing it as missing — this would likely have prevented
   C019, C023, and C027.
2. Continue running `rule_checker.py` on every case regardless of AI
   confidence — it independently caught the C009 mask issue this cycle.
3. Keep human review mandatory for every "medium" or "low" confidence
   response before any fix is applied in the lab.
