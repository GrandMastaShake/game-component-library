--!strict
-- Adapter for component.schema.json id: social.trade_coordinator
-- Thin translation layer over roblox-modular-lib/src/TradeCoordinator.lua
-- No gameplay logic lives here — this only maps schema inputs/outputs/events
-- onto the real module's function names once it is vendored into this repo.

local Adapter = {}
Adapter.componentId = "social.trade_coordinator"

export type TradeCoordinatorConfig = {
	confirmTimeoutSeconds: number?,
}

-- Inputs (per schema): confirmTimeoutSeconds (default 30)
-- Outputs (per schema): activeTrades (array)
-- Emits: social.tradeValidated, social.tradeCommitted, social.tradeRejected
-- ListensTo: social.tradeOpened
-- Dependencies (per schema): inventory.core_inventory, economy.currency
function Adapter.new(config: TradeCoordinatorConfig?)
	local cfg = config or {}
	local confirmTimeoutSeconds = cfg.confirmTimeoutSeconds or 30

	local self = {
		_confirmTimeoutSeconds = confirmTimeoutSeconds,
		activeTrades = {},
	}

	-- Real wiring: require the actual TradeCoordinator module, forward its
	-- native events (whatever they're internally named) onto the schema's
	-- social.tradeValidated / social.tradeCommitted / social.tradeRejected
	-- event names, and subscribe to social.tradeOpened from the
	-- trade_remote_handler adapter to kick off validation.

	return self
end

return Adapter
