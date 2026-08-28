# Roblox Adapter Integration

The schema library and `roblox-modular-lib` deliberately remain separate repositories. The adapter layer connects them using dependency injection rather than a hard-coded cross-repository `require()` path.

## Verified constructors

The following calls were verified against the current `roblox-modular-lib` source on `main`:

```lua
Inventory.new(eventBus, maxSlots)
TradeCoordinator.new(eventBus, deps, config)
```

`src/init.lua` exports `Inventory`, `TradeSystem`, `TradeCoordinator`, and `TradeRemoteHandler` from the source package. The consuming game should import them according to its own Rojo/Wally/Studio layout and provide them to `AdapterRuntime`.

## Minimal host wiring

```lua
local GameLib = require(path.to.RobloxModularLib)
local AdapterRuntime = require(path.to.GameComponentLibrary.AdapterRuntime)
local CoreInventoryAdapter = require(path.to.GameComponentLibrary["inventory.core_inventory.adapter"])
local TradeCoordinatorAdapter = require(path.to.GameComponentLibrary["social.trade_coordinator.adapter"])

local runtime = AdapterRuntime.new(eventBus, {
    Inventory = GameLib.Inventory,
    TradeCoordinator = GameLib.TradeCoordinator,
    CurrencySystem = GameLib.CurrencySystem,
    TradeSystem = GameLib.TradeSystem,
    TradeRemoteHandler = GameLib.TradeRemoteHandler,
})

local inventory = CoreInventoryAdapter.new(runtime, { maxSlots = 20 })
local tradeCoordinator = TradeCoordinatorAdapter.new(runtime, tradeDeps, {
    confirmTimeoutSeconds = 30,
})
```

## Why injection matters

- The game owns module resolution and controls its Rojo/Wally/Studio tree.
- `game-component-library` stays platform-contract-focused instead of vendoring the Roblox implementation.
- Adapters can be tested with mocks.
- The original modules remain the source of truth for their dependency types and runtime behavior.

## Next extraction targets

Before expanding beyond construction-level integration, extract and confirm:

1. Public methods and emitted event names for `Inventory.lua`.
2. The `TradeCoordinatorDeps` structural type and configuration keys.
3. Event contracts in `TradeSystem.lua` and `TradeRemoteHandler.lua`.
4. Public exports and exact names in `src/init.lua`.

Do not replace the remaining adapter TODOs with guessed function names. Add a source-backed adapter only after its public API has been verified.
