# Genre Component Map — 35 Genres

Working brainstorm for expanding the Game Component Library from "one game
(pet-survival) done well" into a genre-spanning component catalog.

Status: Pass 1 shipped ([PR #20](https://github.com/GrandMastaShake/game-component-library/pull/20) — squads A–D, genres #1–28 + exploration). Pass 2 (squads E, F, G) covers the remaining 15, including the Tile-Matching / Logic Puzzle split and Casino & Gacha as the slot-30 winner. Learning/Educational is deferred as its own initiative.

## Context: what we already have

- **79 component descriptors** in 13 schema-fixed categories:
  `movement, combat, inventory, economy, social, world, ui, pets,
  progression, persistence, presentation, housing, utility`.
- **11 compounds** (multi-system loops) and a validated example game
  (Pet Survival) that proves the descriptor → compound → manifest →
  readiness pipeline end to end.
- **4 view modes already built** in the app: top-down, 2D side-scroll,
  voxel, isometric. Every genre pack below declares which view(s) it
  defaults to — the view is a lens for component selection, not a
  separate component set.
- **Schema constraint:** new components must slot into the existing 13
  categories (the enum is fixed in `component.schema.json`). If a genre
  genuinely needs a new category, that's a schema PR, not a sneak-in.

## How to read each entry

- **Loop** — the minimum repeatable player cycle the pack must support.
- **View** — default view mode(s) from the four already built.
- **Reuse** — existing component ids that carry real weight in this genre.
- **New** — proposed new descriptors (naming follows `PascalCase`).
  `★` = genre-defining; without it the genre doesn't exist.

Naming convention for genre ids: `genre.<slug>` (e.g. `genre.platformer`).

---

## Squad A — Precision Action

### 1. Platformer
- **Loop:** traverse → jump/avoid → collect → reach goal.
- **View:** 2D side-scroll (primary), voxel.
- **Reuse:** JumpCore, GroundSensor, WallInteraction, LedgeGrab, DashAbility, PhysicsCore, LevelGoal, HazardVolume, CameraFollow, TimerSystem.
- **New:** `CoyoteJumpBuffer` ★ (coyote time + jump buffering feel layer), `MovingPlatform` (path-based carriers, ride detection), `CollectibleScatter` (coins/rings w/ magnet + respawn rules), `SpringLauncher`, `CheckpointFlag`.

### 2. Puzzle Platformer
- **Loop:** observe → manipulate world state → traverse → exit.
- **View:** 2D side-scroll, isometric.
- **Reuse:** everything in Platformer + BehaviorFSM, CommandBus.
- **New:** `SwitchMechanism` ★ (levers/plates/buttons w/ state broadcast), `DoorGate` (multi-condition locks), `PushableBlock`, `PressurePlate` (weighted: player/crate/both), `TeleportPair`, `RewindTime` (Braid-style state history — also the seed of a future "time-limit" modifier kit).

### 3. Metroidvania
- **Loop:** explore → hit ability gate → backtrack with new power → unlock region.
- **View:** 2D side-scroll.
- **Reuse:** Platformer kit + Minimap, SaveSystem, XPLeveling, SkillsTree.
- **New:** `AbilityGate` ★ (door/terrain that checks acquired powers), `InterconnectedMapGraph` (room graph, lock-and-key topology, map reveal), `PowerUpGrant` (double-jump/wall-cling/etc. as acquirable movement mutations), `BossRoomSeal`, `MapRevealSystem`.

### 4. Fighting
- **Loop:** neutral → footsies → combo/punish → round end.
- **View:** 2D side-scroll (versus).
- **Reuse:** CharacterBody, MeleeBasic, DamageResolver, StatusEffects, BehaviorFSM, HUD, ScreenShake, ParticleSystem.
- **New:** `HitboxHurtbox` ★ (frame-data-accurate boxes), `ComboChain` ★ (cancel windows, input buffer, motion inputs), `BlockParrySystem`, `RoundManager` (best-of-N, timer, round states), `SuperMeter`, `ThrowTech`.

### 5. Rhythm
- **Loop:** chart scrolls → hit inputs on beat → accuracy score → grade.
- **View:** view-agnostic (UI-forward); works over any backdrop.
- **Reuse:** AudioSystem, HUD, TimerSystem, XPLeveling, Leaderboard.
- **New:** `BeatClock` ★ (sample-accurate song position, latency calibration), `NoteHighway` ★ (chart data → scrolling note lanes), `JudgementWindow` (perfect/good/miss timing tiers), `ComboMultiplier`, `ChartLoader` (difficulty tiers, beatmaps as data).

---

## Squad B — Combat & Stakes

### 6. Shooter
- **Loop:** acquire target → fire/manage ammo → take cover/reposition → clear.
- **View:** top-down (twin-stick), voxel (first-person via FirstPersonCamera).
- **Reuse:** DamageResolver, StatusEffects, HUD, CameraFollow, FirstPersonCamera, ScreenShake, ParticleSystem, PathfindingSystem.
- **New:** `ProjectileSystem` ★ (hitscan + ballistic, spread/recoil), `WeaponLoadout` ★ (slots, swap, fire modes), `AmmoEconomy` (mag/reserve/reload), `CoverSystem`, `AimAssist` (configurable), `HitFeedback` (hitmarkers, damage direction).

### 7. Battle Royale
- **Loop:** drop → loot → zone shrinks → last one standing.
- **View:** top-down, voxel.
- **Reuse:** Shooter kit + LootTable, CoreInventory, Minimap, PartySystem, Leaderboard.
- **New:** `ZoneCollapse` ★ (shrinking safe area, escalating damage ticks), `DropDeployment` (skydive/spawn selection), `MatchLifecycle` ★ (lobby→drop→endgame→podium state machine), `SpectatorMode`, `DownedRevive`.

### 8. Survival Adventure
- **Loop:** gather → craft → eat/shelter → push deeper.
- **View:** top-down, voxel, isometric.
- **Reuse:** CraftingBench, CoreInventory, LootTable, TerrainGenerator, DayNightCycle, WeatherSystem, HazardVolume, SaveSystem.
- **New:** `VitalStats` ★ (hunger/thirst/temperature/stamina drains), `HarvestNode` (choppable/minable resource nodes w/ respawn), `BuildPlacement` (grid-snap shelter/furniture), `FireWarmth` (heat sources vs temperature), `SpoilageSystem`.

### 9. Survival Horror
- **Loop:** explore dread space → ration scarce resources → evade/fight → survive setpiece.
- **View:** top-down, voxel (first-person), isometric (fixed-angle).
- **Reuse:** Survival kit minus comfort + VisionSystem, AtmosphereSystem, AudioSystem, BehaviorFSM, MobPatrol.
- **New:** `FearSanityMeter` ★ (accumulating dread w/ gameplay effects), `ScarcityInventory` ★ (hard slot limits, forced triage), `StalkerAI` (relentless pursuer w/ offscreen telegraphing), `HidingSpot` (lockers/closets w/ detection rules), `LimitedSave` (ink-ribbon style save tokens).

### 10. Sports
- **Loop:** possession → advance → score → reset.
- **View:** top-down, side-scroll.
- **Reuse:** CharacterBody, RunControl, PhysicsCore, TimerSystem, Leaderboard, HUD, BehaviorFSM.
- **New:** `BallCarrier` ★ (possession, passing, dribble/kick physics), `GoalZone` ★ (scoring volumes + score rules), `TeamRoster` (positions, AI roles), `MatchClock` (periods, overtime), `RefereeRules` (fouls, offsides, out-of-bounds), `SkillMoveSet`.

---

## Squad C — RPG Family

### 11. Action RPG
- **Loop:** fight in real time → loot → build character → bigger fight.
- **View:** isometric (Diablo-style), top-down.
- **Reuse:** MeleeBasic, DamageResolver, StatusEffects, EquipmentSlots, XPLeveling, SkillsTree, LootTable, QuestLog, SlottedBag.
- **New:** `HotbarAbilities` ★ (cooldown-based active skills w/ resource costs), `AffixLootGenerator` ★ (item rarity + random stat rolls), `EnemyTierScaling`, `PotionBelt`, `WaypointTravel`.

### 12. CRPG
- **Loop:** party of builds → tactical encounters → dialogue choices → branching story.
- **View:** isometric.
- **Reuse:** PartySystem, DialogueBox, QuestLog, SkillsTree, StatusEffects, SaveSystem.
- **New:** `PartyFormation` ★ (multi-character control handoff), `DialogueTreeEngine` ★ (branching nodes w/ skill checks + consequence flags), `AttributeSheet` (STR/DEX/INT-style stats feeding checks), `ReputationSystem`, `RestCamp` (party resource reset w/ ambush risk).

### 13. Dungeon Crawler
- **Loop:** enter floor → rooms/corridors → traps/treasure/boss → descend.
- **View:** top-down, voxel (first-person grid-step), isometric.
- **Reuse:** dd-* lineage (dungeon/encounter generators exist as app TS — candidates for `upstream-mapped`), PathfindingSystem, LootTable, HazardVolume, VisionSystem.
- **New:** `FloorDescent` ★ (procedural floor stack w/ seed continuity), `RoomTemplate` (hand-authored room stamps in procedural layout), `TrapSystem` (detect/disarm/trigger), `FogOfWarReveal`, `BossEncounterScript`.

### 14. Open World (folds Sandbox RPG)
- **Loop:** roam → discover POI → engage content on your terms → world reacts.
- **View:** voxel, top-down.
- **Reuse:** ChunkManager, TerrainGenerator, BiomeSystem, WorldBuilder, DayNightCycle, WeatherSystem, MobPatrol, LODSystem, QuestLog.
- **New:** `PointOfInterestNetwork` ★ (discoverable locations, map markers, fast-travel unlock), `StreamingWorldLoader` ★ (seamless chunk paging w/ entity lifecycles), `DynamicEncounterSpawner` (level-appropriate pop-in), `WorldStateFlags` (persistent world changes), `VehicleSummon`.

### 15. Turn-Based Tactics
- **Loop:** scout → position units → action economy per turn → objective.
- **View:** isometric, top-down.
- **Reuse:** TileGrid, BehaviorFSM, DamageResolver, StatusEffects, VisionSystem, CommandBus.
- **New:** `TurnOrderQueue` ★ (initiative/AP-based sequencing), `GridMovementRange` ★ (movement+attack overlays, pathing costs), `ActionPointEconomy` (move/act/item budgets), `CoverBonusGrid`, `TypeChart` (elemental/strength-weakness multipliers — shared with Monster Taming), `PermadeathFlag` (optional roguelike bridge).

---

## Squad D — Machines & Logistics

### 16. Exploration / Collectathon
- **Loop:** wander → spot shiny → reach it (movement puzzle) → completion %.
- **View:** voxel, isometric.
- **Reuse:** Platformer kit (3D variant), CollectibleScatter (#1), Minimap, LevelGoal.
- **New:** `CompletionTracker` ★ (per-region collectible %, 100%-run support), `HiddenAlcove` (secret detection + reward fanfare), `GuidedHintSystem` (progressive "hot/cold" ping), `GrappleTraversal`, `PhotoMode`.

### 17. Driving / Racing
- **Loop:** launch → corner/drift → overtake → finish/place.
- **View:** top-down, voxel (chase cam).
- **Reuse:** VehicleBasic, PhysicsCore, TimerSystem, Leaderboard, ScreenShake, Minimap.
- **New:** `VehicleTuning` ★ (accel/grip/drift params per vehicle), `TrackCircuit` ★ (spline track, checkpoints, lap validation), `DriftScoring`, `RubberBandAI`, `GhostReplay` (recorded input playback).

### 18. Vehicular Combat
- **Loop:** drive → weaponize → ram/shoot → last vehicle rolling.
- **View:** top-down, voxel.
- **Reuse:** Driving kit + ProjectileSystem (#6), DamageResolver, HazardVolume.
- **New:** `VehicleMountWeapons` ★ (hardpoints, turret arcs, ammo), `RamDamageModel` (speed-mass collision damage, crumple states), `ArenaHazards`, `VehicleDamageStates` (performance degradation w/ visual damage).

### 19. Driver RPG  *(the mashup — this one slaps if tuned right)*
- **Loop:** take driving gigs → earn → upgrade ride & driver → rep unlocks tiers → story races.
- **View:** voxel (driving) + top-down (garage/map).
- **Reuse:** VehicleTuning (#17), Currency, XPLeveling, SkillsTree, QuestLog, DialogueBox, ReputationSystem (#12), PointOfInterestNetwork (#14).
- **New:** `DriverProgression` ★ (driver skills distinct from vehicle stats — cornering style, focus meter), `GarageManagement` ★ (multi-vehicle ownership, part installation, visual customization), `GigEconomy` (procedural courier/race/getaway contracts), `StreetRepTiers` (faction rep gates events + shop stock), `WagerRaces` (pink-slip / virtual-cash stakes).

### 20. Transport Tycoon
- **Loop:** build route → assign vehicles → optimize throughput → expand network.
- **View:** isometric, top-down.
- **Reuse:** TeamResources, Currency, ProductionQueue, PathfindingSystem, TileGrid, Minimap.
- **New:** `RouteNetwork` ★ (node-edge routes w/ schedules), `CargoManifest` (goods types, supply/demand pricing), `DepotDispatch` (vehicle assignment + maintenance cycles), `PassengerFlow` (station catchment simulation), `NetworkEfficiencyScore`.

---

## Squad E — Sims & Creatures

### 21. Construction & Management Sim
- **Loop:** zone/place → citizens arrive → balance economy → unlock tier.
- **View:** isometric.
- **Reuse:** TileGrid, IsoProjection, Currency, TeamResources, ProductionQueue, ObjectPlacer, EnvironmentBuilder.
- **New:** `ZonePlanner` ★ (R/C/I-style zoning w/ growth rules), `CitizenAgentSim` ★ (needs-driven agents: home→work→shop loops), `ServiceCoverage` (power/water/police radius maps), `DemandIndicators` (RCI bars + advisory events), `DisasterEvent`.

### 22. Life Sim
- **Loop:** fulfill needs → build relationships → advance career/skills → decorate home.
- **View:** isometric, top-down.
- **Reuse:** HomeSystem, CitizenAgentSim (#21), DialogueBox, SkillsTree, DayNightCycle, SaveSystem.
- **New:** `NeedsDecay` ★ (bladder/energy/fun meters driving autonomy), `RelationshipGraph` ★ (affinity, grudges, romance states), `CareerTrack` (job levels w/ schedule + promotion), `MoodletSystem` (stacking state modifiers from recent events), `FurnishMode`.

### 23. Pet Sim  *(half-built — our proving ground)*
- **Loop:** hatch → care → train → show/trade.
- **View:** top-down, isometric.
- **Reuse:** PetCompanion, EggHatchery, PetHatchPresenter, HomeTradeStand + the four pet compounds. **This genre is our reference for "done."**
- **New:** `PetNeedsPanel` (feeding/cleanliness/play meters), `PetTrainingMinigame`, `BreedGenealogy` (trait inheritance), `PetShowJudge` (scored competitions).

### 24. Monster Taming
- **Loop:** encounter wild → weaken → capture → build team → battle gyms.
- **View:** top-down, isometric.
- **Reuse:** Pet Sim kit + PartySystem, TurnOrderQueue (#15), TypeChart (#15), XPLeveling, SlottedBag.
- **New:** `CaptureMechanic` ★ (weaken→throw→shake→catch probability), `MonsterDex` ★ (seen/caught registry w/ completion rewards), `EvolutionTree` (branching evolution conditions), `TeamComposition` (party of 6 + storage boxes), `GymChallenge` (gauntlet w/ badge grants).

### 25. Idle / Incremental
- **Loop:** produce → spend on multiplier → prestige → repeat faster.
- **View:** UI-forward; any backdrop.
- **Reuse:** Currency, ProductionQueue, TimerSystem, SaveSystem, NotificationToast.
- **New:** `OfflineEarnings` ★ (catch-up calc on return, capped), `PrestigeReset` ★ (meta-currency conversion + permanent multipliers), `AutoProducer` (generator tiers w/ scaling cost curves), `UpgradeTree` (exponential cost, milestone unlocks), `AchievementMilestones`.

---

## Squad F — Table & Chance

### 26. Card / Deckbuilder
- **Loop:** draw hand → spend energy → play cards → reward draft → thin/refine deck.
- **View:** UI-forward over any view.
- **Reuse:** CoreInventory (deck as inventory), LootTable (draft rewards), DamageResolver, StatusEffects, CommandBus.
- **New:** `DeckManager` ★ (draw/discard/exhaust piles, shuffle), `CardEffectDSL` ★ (data-driven effects: cost, target, trigger), `EnergyPerTurn`, `DraftRewardScreen`, `RelicPassive` (run-scoped modifiers).

### 27. Board Game
- **Loop:** roll/activate → move token → resolve space → pass turn.
- **View:** top-down, isometric.
- **Reuse:** TileGrid (as track), TimerSystem, PartySystem (hotseat/multiplayer), Currency, HUD.
- **New:** `DiceRollResolver` ★ (seeded, auditable), `BoardTrackPath` ★ (branching tracks, space effects), `TokenMovement` (lap tracking, captures), `CardDrawDeck` (chance/event decks), `HotseatTurnPass`.

### 28. Roguelike
- **Loop:** run starts → procedural floors → build draft → die → meta-progress.
- **View:** top-down, isometric, side-scroll (Spelunky variant).
- **Reuse:** FloorDescent (#13), AffixLootGenerator (#11), PermadeathFlag (#15), Dungeon Crawler kit.
- **New:** `RunSeedManager` ★ (deterministic run from seed, daily-run support), `RunMetaProgression` ★ (unlock pool persists between deaths), `DraftOnLevelUp` (choose-1-of-3 on run milestones), `DeathSummary` (run stats, unlock credits).

### 29. Tile-Matching  *(match-3 family — split from Logic Puzzle in pass 2 planning)*
- **Loop:** inspect grid → swap → cascade/score → level target.
- **View:** UI grid; 2D.
- **Reuse:** TileGrid, TimerSystem, Leaderboard, XPLeveling (level map), AudioSystem.
- **New:** `MatchResolver` ★ (match detection, cascades, special pieces), `SwapValidator` (legal-move check + shuffle-on-deadlock), `LevelObjectiveSet` (score/collect/clear targets w/ move limits), `BoosterPieces` (earned/created power pieces), `CascadeScoring`.

### 30. Casino & Gacha  *(slot-30 winner — chance games pack)*
- **Loop:** earn/pull → reveal → collect or convert duplicates → pity builds → banner rotates.
- **View:** UI-forward; presentation-heavy reveal sequences.
- **Reuse:** Currency, LootTable, NotificationToast, SaveSystem, AudioSystem, ParticleSystem.
- **New:** `ProbabilityCore` ★ (seeded, auditable weighted RNG with published rates), `GachaBanner` ★ (rotating rate-up pools, pull counters, spark/exchange), `PitySystem` (hard/soft pity per banner), `DuplicateConverter` (dupes → shards/currency), `SlotReelResolver` (reel strips + paylines, honest presentation).
- **Hard rule:** virtual currency only — no real-money wagering, no cash-out, ever. `WagerRaces` (#19) follows the same rule.

---

## Squad G — Cerebral & Sandbox (honorable tier)

### 31. Logic Puzzle  *(sudoku-like: sudoku, nonogram, picross, kakuro — own pack)*
- **Loop:** given constraints → deduce → fill cells → puzzle complete.
- **View:** UI grid; 2D.
- **Reuse:** TileGrid, TimerSystem, Leaderboard, SaveSystem (progress), AudioSystem.
- **New:** `LogicGridEngine` ★ (constraint-satisfaction core: generator + validator + solution-uniqueness check), `HintSystem` ★ (tiered hints from candidate-elimination up to strategy explanation), `PuzzleDifficultyRater` (grades generated puzzles by techniques required), `PencilMarks` (candidate notation), `DailyPuzzleSeed`.

### 32. Point & Click / Escape Room
- **Loop:** examine scene → collect clues/items → combine → unlock next space.
- **View:** isometric, side-scroll-2d.
- **Reuse:** DialogueTreeEngine (#12), CoreInventory, DialogueBox, SaveSystem, AtmosphereSystem.
- **New:** `HotspotLayer` ★ (clickable regions w/ context-sensitive cursor), `InventoryCombine` ★ (item+item and item+hotspot rules), `PuzzleLockChain` (multi-stage interdependent locks), `RoomEscapeTimer` (optional pressure mode), `NarrativeJournal` (auto clue log).

### 33. Text / Interactive Fiction
- **Loop:** read passage → choose/type → world state shifts → next passage.
- **View:** UI-forward.
- **Reuse:** DialogueBox, SaveSystem, AudioSystem, AtmosphereSystem.
- **New:** `PassageEngine` ★ (node graph of text passages w/ live state interpolation), `ChoiceConsequence` ★ (flags + branch conditions), `TextParserFallback` (verb-noun parser mode for parser-IF), `StoryStats` (tracked variables surfaced to the reader), `SaveBookmark` (named multi-slot checkpoints).

### 34. Physics Sandbox
- **Loop:** spawn/join parts → apply forces → watch emergent behavior → iterate.
- **View:** side-scroll-2d, voxel.
- **Reuse:** PhysicsCore, BehaviorFSM, CommandBus, ObjectPlacer, ParticleSystem.
- **New:** `RagdollSystem` ★ (multi-body limbs w/ constraints), `JointBuilder` ★ (hinges/springs/pistons composable into contraptions), `FluidBuoyancy`, `ContraptionSaveLoad` (shareable builds), `ForceVisualizer` (debug/pedagogy overlay).

### 35. Programming Game
- **Loop:** read puzzle spec → write/visual-script a solution → run against test harness → optimize.
- **View:** top-down, ui-forward.
- **Reuse:** BehaviorFSM, CommandBus, HUD, Leaderboard, LevelGoal.
- **New:** `VisualNodeScript` ★ (node-graph scripting w/ type-checked wires), `CodePuzzleValidator` ★ (test-case harness w/ pass/fail telemetry), `RobotCommandQueue` (compiled program → queued actor execution), `SandboxedVM` ★ (resource-capped script execution — the safety story: memory/time/op limits, no host access), `DebuggerOverlay` (breakpoints, watch values).

---

## The Bench (deferred)

| Genre | Status | Signature components when picked up |
|---|---|---|
| Learning / Educational | **Deferred — its own initiative.** A pedagogy platform (curriculum mapping, spaced repetition, assessment) more than a component pack; deserves a dedicated design pass rather than a squad slot | `QuizEngine`, `SpacedRepetition`, `CurriculumMap` |

**Cross-cutting note:** "time limit" from the original brainstorm isn't a
genre — it's a modifier. `TimerSystem` + `RewindTime`,
`RoomEscapeTimer`, and `MatchClock` cover it as a composable layer over
any genre pack.

## Swarm plan

**Pass 1 — SHIPPED** ([PR #20](https://github.com/GrandMastaShake/game-component-library/pull/20)):
Squads A–D, 20 genre packs (#1–28 plus exploration/collectathon), 103 new
components. Catalog: 79 → 182, both validators green.

**Pass 2 — 3 squads × 5 genres (15 packs):**

| Squad | Genres |
|---|---|
| E — Sims & Creatures | Construction & Management, Life Sim, Pet Sim, Monster Taming, Idle |
| F — Table & Chance | Card/Deckbuilder, Board, Roguelike, Tile-Matching, Casino & Gacha |
| G — Cerebral & Sandbox | Logic Puzzle, Point & Click/Escape Room, Text/IF, Physics Sandbox, Programming |

Each squad delivers, per genre:

1. `genres/<slug>.genre.json` validating against `genre.schema.json`.
2. `components/<category>/<Name>.component.json` for every **new**
   component, schema-valid, `provenance: library-native`, all five
   runtime targets `unmapped`.
3. Everything passes `tools/validate_component_graph.py` and
   `tools/validate_compounds.py`.
4. Lands on a branch + PR, never direct to main.
