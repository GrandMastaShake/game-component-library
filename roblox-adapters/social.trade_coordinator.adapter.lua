--!strict
-- Schema adapter: social.trade_coordinator
-- Verified source constructor: TradeCoordinator.new(eventBus, deps, config)
-- Source: roblox-modular-lib/src/TradeCoordinator.lua

local Adapter = {}
Adapter.componentId = "social.trade_coordinator"

export type Config = {
	confirmTimeoutSeconds: number?,
}

export type Runtime = {
	eventBus: { Emit: (self: any, eventName: string, payload: any) -> () },
	RequireSource: (self: any, sourceName: string) -> any,
	Emit: (self: any, eventName: string, payload: any) -> (),
}

-- `deps` is intentionally supplied by the host game. TradeCoordinator's real
-- dependency shape is defined by roblox-modular-lib and should remain the
-- source of truth rather than being duplicated or guessed in this repo.
-- inputs: confirmTimeoutSeconds (translated into host config by the caller)
-- outputs: activeTrades (source-owned)
-- emits/listensTo: mapped after the host EventBus event names are extracted.
function Adapter.new(runtime: Runtime, deps: any, config: Config?)
	local TradeCoordinator = runtime:RequireSource("TradeCoordinator")
	local cfg = config or {}

	-- This is a verified call against the live source signature.
	local backing = TradeCoordinator.new(runtime.eventBus, deps, cfg)

	return {
		componentId = Adapter.componentId,
		backing = backing,
		config = cfg,
	}
end

return Adapter
