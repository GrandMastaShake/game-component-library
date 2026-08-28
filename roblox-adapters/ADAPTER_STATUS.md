# Roblox Adapter Status

## Proven, implemented paths

| Component | Runtime | Status |
|---|---|---|
| `inventory.core_inventory` | Upstream `Inventory.new(eventBus, maxSlots)` | Constructor source-verified; adapter scaffolded |
| `economy.currency` | Project-supplied currency implementation | Adapter boundary scaffolded |
| `social.trade_coordinator` | Upstream `TradeCoordinator.new(eventBus, deps, config)` | Constructor source-verified; factory scaffolded |
| `pets.egg_hatchery` | `native/EggHatchery.lua` | Library-native, deterministic tests added |
| `ui.pet_hatch_presenter` | `native/PetHatchPresenter.lua` | Library-native, deterministic tests added |
| `ui.notification_toast` | `ui.notification_toast.adapter.lua` | Event bridge implemented; renderer is injected by consuming game |

## Evidence boundary

The upstream `EventBus` exposes `Subscribe(eventName, callback)` and supports the notification bridge subscription model. UI construction, tweening, ScreenGui placement, and per-player routing remain consuming-game responsibilities through the injected renderer.

## Still needed for a playable hatch demo

1. A Roblox client/server bootstrap that instantiates Inventory, EggHatchery, PetHatchPresenter, and NotificationToastAdapter with the project EventBus.
2. A renderer implementation whose `Show(payload)` creates/displays a toast for `payload.playerId`.
3. A persistence adapter subscription to `pets.hatched`.
4. Live Studio playtesting, including RemoteEvent request validation and DataStore failure behavior.
