# Roblox Integration

## Dependency-injection boundary

This repository deliberately avoids hard-coded cross-project `require()` paths. The consuming Roblox project supplies upstream modules, EventBus, authoritative services, persistence boundary, and UI renderer through its own Rojo, Wally, or Studio layout.

## Native Pet Hatching Flow

`native/PetHatchFlow.lua` composes the native hatching modules on the **server**:

```text
validated server transport
  → flow:Hatch(player.UserId)
  → EggHatchery verifies inventory/currency and chooses with server RNG
  → pets.hatched
  → PetHatchPresenter emits ui.notificationRequested
  → injected markPersistenceDirty callback
```

```lua
local flow = PetHatchFlow.new(eventBus, {
    inventory = authoritativeInventory,
    currency = authoritativeCurrency,
    random = Random.new(),
    markPersistenceDirty = function(playerId, payload)
        persistenceService:MarkDirty(playerId, "pet-hatch", payload)
    end,
}, hatchConfig)
flow:Start()
```

Call `flow:Hatch(player.UserId)` only after deriving identity from authenticated server transport. Do not accept a client-provided user ID, currency balance, egg count, hatch table, or random roll.

## Client notification bridge

Construct `NotificationToastAdapter` in the appropriate UI context with a renderer implementing `renderer:Show(payload)`. The renderer owns ScreenGui placement, tweening, localization, assets, and client filtering. The adapter owns only the normalized event-to-renderer bridge.

## Evidence status

`Inventory.new(eventBus, maxSlots)`, `TradeCoordinator.new(eventBus, deps, config)`, and `EventBus:Subscribe(eventName, callback)` have been source-verified upstream. A consuming project must still validate its RemoteEvent topology, persistence API, and UI renderer in Roblox Studio.
