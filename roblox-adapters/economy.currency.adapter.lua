--!strict
-- Adapter for component.schema.json id: economy.currency
-- Wraps roblox-modular-lib/src/CurrencySystem.lua
-- NOTE: real CurrencySystem.lua API not yet verified in this session; see TODOs.

local Adapter = {}
Adapter.componentId = "economy.currency"

export type CurrencyConfig = {
	currencyName: string?,
	startingBalance: number?,
}

-- Inputs (per schema): currencyName (default "Coins"), startingBalance (default 0)
-- Outputs (per schema): balance (number)
-- Emits: economy.earned, economy.spent, economy.insufficientFunds
-- ListensTo: social.tradeCommitted
function Adapter.new(player: Player, config: CurrencyConfig?)
	local cfg = config or {}
	local self = {
		_player = player,
		_currencyName = cfg.currencyName or "Coins",
		balance = cfg.startingBalance or 0,
	}

	-- TODO: require the real CurrencySystem module and bind it to this player,
	-- e.g. local Currency = require(RobloxModularLib.CurrencySystem)

	return self
end

-- TODO: verify against real API; should emit economy.earned on success.
function Adapter:Earn(amount: number)
	self.balance += amount
end

-- TODO: verify against real API; should emit economy.insufficientFunds if balance < amount.
function Adapter:Spend(amount: number): boolean
	if self.balance < amount then
		return false
	end
	self.balance -= amount
	return true
end

return Adapter
