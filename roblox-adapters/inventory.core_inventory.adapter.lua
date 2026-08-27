--!strict
-- Adapter for component.schema.json id: inventory.core_inventory
-- Wraps roblox-modular-lib/src/Inventory.lua
-- NOTE: exact method names below are placeholders. This repo has not yet
-- vendored roblox-modular-lib as a dependency, so the real Inventory.lua
-- API surface has not been verified. Replace TODO-marked lines once it is.

local Adapter = {}
Adapter.componentId = "inventory.core_inventory"

-- Inputs (per schema): initialItems (array, default {})
-- Outputs (per schema): itemCount (number)
-- Emits: inventory.itemAdded, inventory.itemRemoved
function Adapter.new(initialItems: {any}?)
	local self = {
		_items = initialItems or {},
		itemCount = 0,
	}
	self.itemCount = #self._items

	-- TODO: require the real Inventory module here, e.g.:
	-- local Inventory = require(RobloxModularLib.Inventory)
	-- self._backing = Inventory.new(initialItems)

	return self
end

-- TODO: verify against real API. Should call the backing module's add function
-- and re-emit inventory.itemAdded through the shared EventBus.
function Adapter:AddItem(item: any)
	table.insert(self._items, item)
	self.itemCount += 1
	-- emit inventory.itemAdded
end

-- TODO: verify against real API.
function Adapter:RemoveItem(item: any)
	-- emit inventory.itemRemoved
end

return Adapter
