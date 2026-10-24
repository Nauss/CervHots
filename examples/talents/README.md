# SYNTHETIC ONLY — no native/game/HUD evidence

`events.jsonl` is generated from invented already-normalized values and a fixed
synthetic journal salt. `SyntheticSelectedTalent` is NOT an actual talent ID.
It illustrates selected → explicit unselected/reset → unknown, with unknown
allies, unknown labels, and an original age of0.25s. No live receipt exists.

From the repository root:

```text
python -B -m cerveau.talents_journal --journal examples/talents/SYNTHETIC/events.jsonl
```

Expected inspection: three historical observations, all labels unknown; never
current permission. The journal is not authenticated truth. A native pipeline
still requires its own fresh receipt, exact hero/build/map/role and context.
