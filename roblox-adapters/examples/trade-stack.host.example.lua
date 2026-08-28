--!strict
-- Host-game example: composition only.
-- Replace `path.to.*` with the consuming game's actual Rojo/Wally/Studio tree.

local GameLib = require(path.to.RobloxModularLib)
local TradeStackFactory = require(path.to.GameComponentLibrary.TradeStackFactory)

-- The game owns the EventBus and must build this object using the exact
-- upstream TradeCoordinatorDeps structural contract.
local coordinatorDeps = {
	-- TODO(source-backed): populate only after extracting the exact fields
	-- from roblox-modular-lib/src/TradeCoordinator.lua.
}

local tradeStack = TradeStackFactory.create(eventBus, {
	Inventory = GameLib.Inventory,
	TradeCoordinator = GameLib.TradeCoordinator,
	CurrencySystem = GameLib.CurrencySystem,
	TradeSystem = GameLib.TradeSystem,
	TradeRemoteHandler = GameLib.TradeRemoteHandler,
}, coordinatorDeps, {
	playerAInventory = { maxSlots = 20 },
	playerBInventory = { maxSlots = 20 },
	coordinatorConfig = { confirmTimeoutSeconds = 30 },
})

-- `tradeStack.playerAInventory.backing` and
-- `tradeStack.playerBInventory.backing` are real instances constructed via
-- Inventory.new(eventBus, maxSlots). `tradeStack.tradeCoordinator.backing` is
-- a real instance constructed via TradeCoordinator.new(eventBus, deps, config).
return tradeStack
