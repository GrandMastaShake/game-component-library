--!strict
-- Schema adapter: inventory.core_inventory
-- Verified source constructor: Inventory.new(eventBus, maxSlots)
-- Source: roblox-modular-lib/src/Inventory.lua

local Adapter = {}
Adapter.componentId = "inventory.core_inventory"

export type Config = {
	maxSlots: number?,
}

export type Runtime = {
	eventBus: { Emit: (self: any, eventName: string, payload: any) -> () },
	RequireSource: (self: any, sourceName: string) -> any,
	Emit: (self: any, eventName: string, payload: any) -> (),
}

-- inputs: initialItems (currently not part of the confirmed source constructor)
-- outputs: itemCount (delegated to the source instance where available)
-- emits: inventory.itemAdded, inventory.itemRemoved (source-event mapping pending)
function Adapter.new(runtime: Runtime, config: Config?)
	local cfg = config or {}
	local Inventory = runtime:RequireSource("Inventory")
	local maxSlots = cfg.maxSlots or 20

	-- This is a verified call against the live source signature.
	local backing = Inventory.new(runtime.eventBus, maxSlots)

	return {
		componentId = Adapter.componentId,
		backing = backing,
		maxSlots = maxSlots,
	}
end

return Adapter
