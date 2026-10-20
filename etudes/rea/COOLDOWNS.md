# Native local cooldowns: qualified partial scope

This is a partial LOT9 source, NOT a completion of LOT9 or permission for other
heroes, allies, enemies, native peers, HUD buttons or controlled vehicles.

## Enabled data

Build98348, DragonShire, native local main hero Sonya, current instance
`BarbarianAncientSpear`, command0, native class9 and current Unit cooldown link
`Abil/BarbarianAncientSpear` only. No static instance ordinal is used as a source
or as a HUD binding. The slot is reported as `native_instance_NOT_HUD_button`.
The case table is a qualification filter, not a base loadout: an absent current
instance never produces a fabricated Spear entry. A known current instance with
changed/unqualified cost binding stays Unknown with no remaining/ready values.

The packet declares `actor_scope=current_native_main_hero` and
`ui_control_body=unknown`. Source actor is the current generation/owner-checked
CPlayer hero-unit pointer, not a cached hero template or a claim about a current
vehicle/control body. `cooldown_ready` means only native remaining equals zero.
`cast_legality=unknown`: mana, health preconditions, range, stun, body controls,
UI availability and global castability are NOT inferred.

Spear charges are only `not_applicable_current_max_zero` when the CURRENT native
cost maximum was actually read as0. A nonzero/unknown maximum remains Unknown,
not a hardcoded zero or a new multi-charge qualification.

## Acquisition and consumer

`hotstate/cooldown_packet.py` resolves actual native identity/team/match and
current main-hero tag, traverses current instances and explicit owning-player
cost overlays, reads current native nodes, and rechecks all successfully read
roots/values before issuing the in-process receipt. Missing nodes, lazy roots
requiring native calls, changed data and unqualified callbacks do not default
to zero. No native function is invoked and no process memory is written.

`hotstate/cooldown_qualification.py` admits only the qualified current binding;
all other native instances are omitted. `cerveau/cooldowns.py` separately rejects
unqualified names and charge claims, requires the receipt/current context and
owner, and exports only allowlisted fields. No pointers, labels, stores or
receipts enter the normalized consumer. Tactical transitions include discrete
readiness/availability, not every changing second or regeneration fraction.

The additive NativeReader/normalizer/key hooks are integrated under the existing
`live.read_current` physical WHOLE budget:8192 requests,1MiB,125ms including typed
context, core, families, final checks, projection and key. Global failures latch
and cannot be hidden by an optional family. No budget threshold was increased.
Current Unit CD root is still a fail-closed prerequisite even when a Player
store could independently exist; this is an availability limit, not fallback.

## Real evidence and provenance

Private operator day004 ran the real consumer path in four bounded windows at
candidate620a41ba9820353bc221dfe500b1e8eee9d9629c. All726 samples replayed with
EXACT physical reads and recorded monotonic calls:349 accepted alive,377 genuine
core-torn refusals. Native Spear observations bracket0 at1033.6875,12.6875 at
1034.25,1.0625 at1045.875,0 at1047.0625;22 positive accepted observations agree
between raw packet, normalized packet and tactical key. Operator supplied HUD
brackets and first alive inspection. Same normal replay has matching native
seed/cache, one local human/nine AI/no active observer; protocol shim declared.
Maxima were4266 requests,111385 bytes,47ms accepted WHOLE on that actual candidate,
not an estimate or sum of family costs. These are historical measurements only.

Original51 source bytes/hashes, raw hashes, ACK/result/release, replay identity
and reports are preserved in ignored `handoffs/t_e3715551/history-r5/manifest.json`
and its source ZIP. Original traces/manifests are not rewritten. No raw files,
pointers or private names are tracked in Git or sent to coach/Telegram.

The narrowed default-source smoke has NO candidate/qualification override:
all726 old ordered reads/time calls consumed exactly, same349/377 outcomes and
same22 positive Spear values. Only unqualified peers are removed and explicit
actor-scope declarations added; the key is correspondingly narrowed. This smoke
is historical, NOT a fresh producer or a new CPU/combined-budget measurement.
Recorded-time receipts are stale under real monotonic time after replay.

## NOT qualified / product gate remains open

- BattleRage current Player max2/available2 is seen in338 whole packets, but no
  activation/regen dynamic cycle occurred in those windows. Full-health attempted
  use did not cast. Earlier r4 DIAGNOSTIC2→1→0→1 is distinct and cannot promote
  whole dynamic charge availability or return FULL2. BattleRage is NOT published.
- Player/Unit charge getters and class6/7/8/9 source paths have fixtures/static
  source work; this is not an all-hero/class/command or Unit multi-charge grant.
- Reset/acceleration, MysticalSpear modifier, transformed/vehicle/control bodies,
  new whole death/respawn, UI slot mapping and total castability remain unproved.
  A death outside a collector is not a captured death/respawn case.
- Native current-instance bitmaps do not establish public HUD permission for
  internal/passive peer abilities. They remain omitted.

Only branch preparation may be accepted after exact independent review. The
integrator alone composes shared hooks with other families/role scopes and must
obtain a NEW operator-only physical WHOLE measurement of the composed pipeline.
Do not sum historical costs, merge/rebase another worker's frozen branch, close
the product LOT9 gate, or start a game solely for missing cooldown coverage.
