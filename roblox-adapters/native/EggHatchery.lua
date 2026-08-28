--!strict
-- Library-native implementation for component id: pets.egg_hatchery
-- Server-authoritative, dependency-injected hatching.

local EggHatchery = {}
EggHatchery.__index = EggHatchery
EggHatchery.componentId = "pets.egg_hatchery"

export type EventBus = { Emit: (self: any, eventName: string, payload: any) -> () }
export type Inventory = {
	HasItem: (self: any, playerId: number, itemId: string, quantity: number) -> boolean,
	RemoveItem: (self: any, playerId: number, itemId: string, quantity: number) -> boolean,
	AddItem: (self: any, playerId: number, itemId: string, quantity: number, metadata: {[string]: any}?) -> boolean,
}
export type Currency = { CanSpend: (self: any, playerId: number, amount: number) -> boolean, Spend: (self: any, playerId: number, amount: number) -> boolean, Refund: (self: any, playerId: number, amount: number) -> () }
export type RandomSource = { NextNumber: (self: any) -> number }
export type HatchEntry = { petId: string, weight: number, rarity: string?, metadata: {[string]: any}? }
export type Config = { eggItemId: string, hatchCost: number?, hatchTable: {HatchEntry} }
export type Dependencies = { inventory: Inventory, currency: Currency?, random: RandomSource }

local function choose(table_: {HatchEntry}, roll: number): HatchEntry
	assert(#table_ > 0 and roll >= 0 and roll < 1, "Invalid hatch table or random roll")
	local total = 0
	for _, entry in table_ do
		assert(type(entry.petId) == "string" and entry.weight > 0, "Invalid hatch entry")
		total += entry.weight
	end
	local threshold, cumulative = roll * total, 0
	for _, entry in table_ do
		cumulative += entry.weight
		if threshold < cumulative then return entry end
	end
	return table_[#table_]
end

function EggHatchery.new(eventBus: EventBus, deps: Dependencies, config: Config)
	assert(eventBus and type(eventBus.Emit) == "function", "EggHatchery requires EventBus.Emit")
	assert(deps and deps.inventory and deps.random, "EggHatchery requires inventory and random dependencies")
	assert(config and type(config.eggItemId) == "string" and #config.eggItemId > 0, "EggHatchery requires eggItemId")
	local cost = config.hatchCost or 0
	assert(cost >= 0, "hatchCost must be >= 0")
	if cost > 0 then assert(deps.currency, "Currency is required for a positive hatch cost") end
	return setmetatable({_eventBus=eventBus,_inventory=deps.inventory,_currency=deps.currency,_random=deps.random,_eggItemId=config.eggItemId,_hatchCost=cost,_hatchTable=config.hatchTable,lastHatchedPet=nil,isHatching=false}, EggHatchery)
end

function EggHatchery:Hatch(playerId: number)
	if self.isHatching then return nil, "hatch-in-progress" end
	if not self._inventory:HasItem(playerId, self._eggItemId, 1) then self._eventBus:Emit("pets.hatchFailed", {playerId=playerId,reason="missing-egg"}); return nil, "missing-egg" end
	if self._hatchCost > 0 and (not self._currency or not self._currency:CanSpend(playerId, self._hatchCost)) then self._eventBus:Emit("pets.hatchFailed", {playerId=playerId,reason="insufficient-funds"}); return nil, "insufficient-funds" end
	self.isHatching = true
	local entry = choose(self._hatchTable, self._random:NextNumber())
	if not self._inventory:RemoveItem(playerId, self._eggItemId, 1) then self.isHatching=false; self._eventBus:Emit("pets.hatchFailed", {playerId=playerId,reason="egg-consume-failed"}); return nil, "egg-consume-failed" end
	local charged = self._hatchCost > 0 and self._currency:Spend(playerId, self._hatchCost)
	if self._hatchCost > 0 and not charged then self._inventory:AddItem(playerId,self._eggItemId,1); self.isHatching=false; self._eventBus:Emit("pets.hatchFailed",{playerId=playerId,reason="charge-failed"}); return nil,"charge-failed" end
	local result = {petId=entry.petId,rarity=entry.rarity,metadata=entry.metadata}
	if not self._inventory:AddItem(playerId,entry.petId,1,{rarity=entry.rarity,hatchMetadata=entry.metadata}) then self._inventory:AddItem(playerId,self._eggItemId,1); if charged then self._currency:Refund(playerId,self._hatchCost) end; self.isHatching=false; self._eventBus:Emit("pets.hatchFailed",{playerId=playerId,reason="pet-grant-failed"}); return nil,"pet-grant-failed" end
	self.lastHatchedPet=result; self.isHatching=false; self._eventBus:Emit("pets.hatched",{playerId=playerId,pet=result,eggItemId=self._eggItemId,hatchCost=self._hatchCost}); return result,nil
end
return EggHatchery
