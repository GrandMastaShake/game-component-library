--!strict
-- Shared runtime for schema-driven Roblox adapters.
-- Source modules are injected by the consuming game rather than required from
-- a hard-coded repository path. This keeps the adapter layer portable across
-- Rojo, Wally, and Roblox Studio layouts.

local AdapterRuntime = {}
AdapterRuntime.__index = AdapterRuntime

export type EventBus = {
	Emit: (self: any, eventName: string, payload: any) -> (),
	On: ((self: any, eventName: string, callback: (payload: any) -> ()) -> any)?,
}

export type SourceModules = {
	Inventory: any?,
	TradeCoordinator: any?,
	CurrencySystem: any?,
	TradeSystem: any?,
	TradeRemoteHandler: any?,
}

export type Runtime = {
	eventBus: EventBus,
	sources: SourceModules,
	RequireSource: (self: Runtime, sourceName: string) -> any,
	Emit: (self: Runtime, eventName: string, payload: any) -> (),
}

function AdapterRuntime.new(eventBus: EventBus, sources: SourceModules): Runtime
	assert(eventBus ~= nil, "AdapterRuntime requires the host game's EventBus")
	assert(type(eventBus.Emit) == "function", "AdapterRuntime EventBus must expose Emit")

	local self = setmetatable({
		eventBus = eventBus,
		sources = sources or {},
	}, AdapterRuntime)

	return self :: any
end

function AdapterRuntime:RequireSource(sourceName: string): any
	local source = self.sources[sourceName :: keyof SourceModules]
	assert(source ~= nil, string.format(
		"Missing source module '%s'. Pass it to AdapterRuntime.new(eventBus, sources).",
		sourceName
	))
	return source
end

function AdapterRuntime:Emit(eventName: string, payload: any)
	self.eventBus:Emit(eventName, payload)
end

return AdapterRuntime
