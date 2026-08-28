# Adapter Capability Matrix

This table separates **source-verified integration** from schema-only scaffolding. A green constructor is not a claim that every public method or event is wired yet.

| Component | Source module | Constructor/API verified | Current adapter state | Next proof required |
|---|---|---:|---|---|
| `inventory.core_inventory` | `Inventory.lua` | `Inventory.new(eventBus, maxSlots)` | Constructor-backed | Public methods and source event names |
| `social.trade_coordinator` | `TradeCoordinator.lua` | `TradeCoordinator.new(eventBus, deps, config)` | Constructor-backed; host supplies exact `deps` | `TradeCoordinatorDeps`, public methods, emitted events |
| `movement.basic_walk` | Host Humanoid API | Not tied to a named upstream source module | Local skeleton | EventBus mapping and host integration test |
| `economy.currency` | `CurrencySystem.lua` | No | Schema-shaped stub | Constructor + Add/Spend/Get API |
| `persistence.save_system` | `SaveSystem.lua` | No | Schema-shaped stub | Constructor + save/load/event API |
| `world.terrain_generator` | `TerrainGenerator.lua` | No | Schema-shaped stub | Generator constructor and generation API |
| `ui.hud` | `UIFramework.lua` | No | Schema-shaped stub | UIFramework constructor and widget/event API |
| `social.trade_remote_handler` | `TradeRemoteHandler.lua` | No | Not yet implemented | Constructor, remote names, lifecycle API |
| `social.trade_window` | `TradeSystem.lua` | No | Schema only | Trade session/UI API and state events |

## Verified assembly boundary

`TradeStackFactory.create(eventBus, sources, coordinatorDeps, config)` is the first source-verified assembly point. It instantiates two inventories and one trade coordinator strictly through confirmed upstream constructor calls.

## Rule for future adapters

A source API may be marked *verified* only when its exact signature has been extracted from the live source or an upstream test. Descriptions, file names, and prior summaries are not enough evidence to write a source call.
