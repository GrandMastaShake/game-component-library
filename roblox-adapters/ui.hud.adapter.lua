--!strict
-- Adapter for component.schema.json id: ui.hud
-- Wraps roblox-modular-lib/src/UIFramework.lua (closest real analog to a HUD shell)
-- NOTE: real UIFramework.lua API not yet verified; TODOs mark unverified calls.

local Adapter = {}
Adapter.componentId = "ui.hud"

export type HudConfig = {
	showHealth: boolean?,
	showCurrency: boolean?,
}

-- Inputs (per schema): showHealth (default true), showCurrency (default true)
-- Outputs (per schema): isVisible (boolean)
-- ListensTo: economy.earned, economy.spent, combat.hit
-- Dependencies (per schema): economy.currency
function Adapter.new(player: Player, currencyAdapter: any, config: HudConfig?)
	local cfg = config or {}
	local self = {
		_player = player,
		_currencyAdapter = currencyAdapter,
		_showHealth = cfg.showHealth ~= false,
		_showCurrency = cfg.showCurrency ~= false,
		isVisible = true,
	}

	-- TODO: require the real UIFramework module and build the actual
	-- ScreenGui/Frame tree, then subscribe to economy.earned / economy.spent /
	-- combat.hit through the shared EventBus to keep the HUD in sync.

	return self
end

return Adapter
