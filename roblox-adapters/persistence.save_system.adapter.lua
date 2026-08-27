--!strict
-- Adapter for component.schema.json id: persistence.save_system
-- Wraps roblox-modular-lib/src/SaveSystem.lua
-- NOTE: real SaveSystem.lua API not yet verified; TODOs mark unverified calls.

local Adapter = {}
Adapter.componentId = "persistence.save_system"

export type SaveConfig = {
	autosaveIntervalSeconds: number?,
}

-- Inputs (per schema): autosaveIntervalSeconds (default 120)
-- Outputs (per schema): lastSaveTimestamp (number), isDirty (boolean)
-- Emits: persistence.saved, persistence.saveFailed
-- ListensTo: inventory.itemAdded, economy.earned, progression.leveledUp
function Adapter.new(config: SaveConfig?)
	local cfg = config or {}
	local self = {
		_autosaveIntervalSeconds = cfg.autosaveIntervalSeconds or 120,
		lastSaveTimestamp = 0,
		isDirty = false,
	}

	-- TODO: require the real SaveSystem module and start its autosave loop.

	return self
end

-- TODO: verify against real API; should emit persistence.saved or persistence.saveFailed.
function Adapter:MarkDirty()
	self.isDirty = true
end

return Adapter
