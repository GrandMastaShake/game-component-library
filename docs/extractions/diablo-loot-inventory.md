# Extraction: Diablo Loot and Inventory

Status: **validated library pack**  
Reference: classic isometric action-RPG loot loops  
Reusable output: `compound.loot_to_build_loop`

## Purpose

Extract the reusable item-economy decisions behind the reference loop, not its
proprietary content. This pack contains no item names, affix tables, artwork,
audio, maps, dialogue, copied code or exact drop data. The contracts are
original and genre-level so they can support other loot-driven games.

## The loop being extracted

```text
Enemy defeated
  → drop director accepts or skips the loot roll
  → loot table selects base content
  → affix generator rolls rarity, affixes and values
  → rolled instance enters the bag
  → full bag leaves it safely on the ground
  → candidate is compared with equipped gear
  → equipment applies item stats and set thresholds react
  → unwanted gear is salvaged into materials
```

The important design insight is that **a drop is not one random operation**.
Drop eligibility, base-item selection and copy quality are three separate
decisions with different tuning owners. Combining them makes drop rates hard
to reason about and encourages duplicate reward logic.

## Ownership map

| Reference pattern | Library owner | Why this boundary |
|---|---|---|
| Chance and number of loot rolls | `inventory.drop_director` **new** | Enemy rewards need an explicit eligibility decision before content generation. |
| Base item or container reward | `inventory.loot_table` | Already owns weighted base-content selection. |
| Rarity, affix count and rolled values | `inventory.affix_loot_generator` | Already owns copy quality; now supports opt-in request-driven rolls. |
| Carried item instances and capacity | `inventory.slotted_bag` | Already owns storage and now accepts the salvage removal event. |
| Low-level item-added signal | `inventory.core_inventory` | Preserves the primitive-to-equipment event path. |
| Floor loot and full-bag overflow | `inventory.ground_items` | Already retains refused items rather than losing them. |
| Candidate-versus-equipped deltas | `inventory.gear_comparison` **new** | Comparison is a calculation, not equipment mutation or tooltip rendering. |
| Actual equipped stats | `combat.equipment_slots` | Already applies each worn item's bonuses. |
| Set thresholds | `combat.gear_sets` | Already owns tiered and stacking set bonuses. |
| Enemy level/reward context | `combat.enemy_tier_scaling` | Already owns difficulty curves, queried synchronously. |
| Gear-to-material conversion | `inventory.salvage_system` **new** | A dedicated item sink, separate from storage and crafting. |

## Why three new components

### `inventory.drop_director`

The affix generator previously listened directly to every defeat. That is a
useful simple mode, but the reference loop needs ordinary enemies to produce
nothing sometimes and higher-tier enemies to guarantee multiple rolls. Drop
Director owns that decision without taking over base-item or affix selection.

The existing generator remains backward-compatible: `triggerMode: onDefeat`
is still the default. This compound opts into `onRequest`.

### `inventory.gear_comparison`

Equipment Slots can answer what one item would add, and Gear Sets can answer
what a set currently gives. Neither computes the complete candidate-minus-
equipped comparison across both items' named stats and set thresholds. The new
component publishes that comparison while refusing to auto-equip on its own.

### `inventory.salvage_system`

Inventory pressure needs a non-destructive decision path besides dropping or
selling. Salvage converts one eligible item instance into materials. The bag
still owns removal and storage; the salvage brick owns only the conversion
recipe and exactly-once event sequence.

## Event flow

```text
combat.damage_resolver
  --combat.entityDefeated--> inventory.drop_director

inventory.drop_director
  --inventory.lootRollRequested--> inventory.affix_loot_generator

inventory.affix_loot_generator
  --inventory.itemGenerated--> slotted bag + gear comparison

inventory.slotted_bag
  --inventory.full--> ground items

inventory.ground_items
  --inventory.itemGranted------> slotted bag
  --inventory.containerOpened--> loot table

inventory.core_inventory
  --inventory.itemAdded--> equipment slots

combat.equipment_slots
  --itemEquipped / itemUnequipped--> gear sets + gear comparison

inventory.salvage_system
  --inventory.itemSalvaged--> slotted bag removes source
  --inventory.itemGranted---> slotted bag stores materials
```

Enemy Tier Scaling and Gear Comparison are calculations, not sequencing
stages. Neither belongs in an event round trip that would delay an answer the
caller needs immediately.

## Configuration extracted from the reference

| Configuration | Default in this pack | Design meaning |
|---|---|---|
| Normal drop chance | 0.25 | Most kills do not create an item, preserving drop significance. |
| Elite/boss chance | 1.0 | Higher-tier encounters reliably pay out. |
| Rolls per drop | 1 / 2 / 3 | Reward quantity scales by enemy tier without changing affix math. |
| Rarity weights | 60 / 25 / 12 / 3 | A configurable starting distribution, not copied game data. |
| Affixes by rarity | 0 / 2 / 4 / 6 | Higher rarity means more build-defining modifiers. |
| Bag slots | 20 | Creates inventory pressure while leaving room for a short run. |
| Dry-streak guarantee | off | Optional protection is explicit rather than hidden in randomness. |
| Protected salvage targets | equipped, locked, quest | Cleanup cannot silently destroy a build or objective. |

Every value is a starting point for a new game, not a claim about a particular
Diablo title, difficulty or patch.

## Acceptance scenarios

1. **Separate drop decision:** normal kills can skip loot; elite and boss guarantees hold.
2. **Separate content and quality:** base table and affix generator each roll only their own concern.
3. **Deterministic replay:** identical seeds and defeat sequences reproduce the complete drop.
4. **Instance integrity:** rarity, affixes and rolled values survive every storage and equipment transition.
5. **No overflow loss:** a full bag leaves the item on the ground for later pickup.
6. **Advisory comparison:** all stat deltas are visible and comparison never mutates equipment.
7. **Set reaction:** thresholds update on equip and unequip without moving item-affix ownership.
8. **Atomic salvage:** one source removal corresponds to exactly one material grant.
9. **Protected items:** equipped, locked and quest items reject salvage by default.
10. **Optional analysis:** comparison and set bonuses can be removed without breaking base loot or equipment.
11. **No duplicate affix roll:** a plain chest reward does not accidentally become combat-generated gear.

## Deliberately deferred

- Shops, gold sinks and item repair
- Crafting recipes that consume salvaged materials
- Item upgrading, rerolling, enchanting and gem sockets
- Loot filters, pickup labels and tooltip presentation
- Trading and shared-stash behavior
- Persistent item-instance storage and migration
- Detailed class restrictions, requirements and skill-specific affixes
- Runtime adapters and server-authoritative anti-duplication implementation
- Exact commercial item tables, names, formulas or balance data

This delivery validates contracts and composition only. Runtime statuses for
the new components remain intentionally `unmapped`.
