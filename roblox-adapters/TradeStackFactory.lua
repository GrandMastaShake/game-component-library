--!strict
-- Verified composition boundary for the inventory + trade-coordinator stack.
-- It calls only constructors confirmed against the current upstream source:
--   Inventory.new(eventBus, maxSlots)
--   TradeCoordinator.new(eventBus, deps, config)
--
-- TradeCoordinator's dependency object remains host-owned until its complete
-- structural type is extracted from the upstream source. Do not guess it here.

local AdapterRuntime = require(script.Parent.AdapterRuntime)
local CoreInventoryAdapter = require(script.Parent["inventory.core_inventory.adapter"])
local TradeCoordinatorAdapter = require(script.Parent["social.trade_coordinator.adapter"])

local TradeStackFactory = {}

export type PlayerInventoryConfig = {
	maxSlots: number?,
}

export type TradeStackConfig = {
	playerAInventory: PlayerInventoryConfig?,
	playerBInventory: PlayerInventoryConfig?,
	coordinatorConfig: { confirmTimeoutSeconds: number? }?,
}

export type TradeStack = {
	runtime: any,
	playerAInventory: any,
	playerBInventory: any,
	tradeCoordinator: any,
}

function TradeStackFactory.create(
	eventBus: AdapterRuntime.EventBus,
	sources: AdapterRuntime.SourceModules,
	coordinatorDeps: any,
	config: TradeStackConfig?
): TradeStack
	assert(sources.Inventory ~= nil, "TradeStackFactory requires sources.Inventory")
	assert(sources.TradeCoordinator ~= nil, "TradeStackFactory requires sources.TradeCoordinator")
	assert(coordinatorDeps ~= nil, "TradeStackFactory requires host-supplied coordinatorDeps")

	local cfg = config or {}
	local runtime = AdapterRuntime.new(eventBus, sources)

	local playerAInventory = CoreInventoryAdapter.new(runtime, cfg.playerAInventory)
	local playerBInventory = CoreInventoryAdapter.new(runtime, cfg.playerBInventory)
	local tradeCoordinator = TradeCoordinatorAdapter.new(
		runtime,
		coordinatorDeps,
		cfg.coordinatorConfig
	)

	return {
		runtime = runtime,
		playerAInventory = playerAInventory,
		playerBInventory = playerBInventory,
		tradeCoordinator = tradeCoordinator,
	}
end

return TradeStackFactory
