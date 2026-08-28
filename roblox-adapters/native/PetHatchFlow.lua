--!strict
-- Server-side composition root for the native Pet Hatching Loop.
-- A transport layer calls Hatch(playerId). UI and persistence are injected.

local EggHatchery = require(script.Parent.EggHatchery)
local PetHatchPresenter = require(script.Parent.PetHatchPresenter)
local PetHatchFlow = {}
PetHatchFlow.__index = PetHatchFlow
PetHatchFlow.componentId = "compound.pet_hatching_loop"

function PetHatchFlow.new(eventBus, dependencies, config)
	assert(eventBus and type(eventBus.Subscribe) == "function", "PetHatchFlow requires EventBus.Subscribe")
	assert(dependencies and dependencies.inventory and dependencies.random, "PetHatchFlow requires inventory and random dependencies")
	return setmetatable({
		_eventBus = eventBus,
		_markPersistenceDirty = dependencies.markPersistenceDirty,
		_presenter = PetHatchPresenter.new(eventBus, { revealSeconds = config.revealSeconds }),
		_hatchery = EggHatchery.new(eventBus, { inventory = dependencies.inventory, currency = dependencies.currency, random = dependencies.random }, config),
		_unsubscribe = nil,
	}, PetHatchFlow)
end

function PetHatchFlow:Start()
	if self._unsubscribe then return end
	self._unsubscribe = self._eventBus:Subscribe("pets.hatched", function(payload)
		self._presenter:Present(payload)
		if self._markPersistenceDirty then self._markPersistenceDirty(payload.playerId, payload) end
	end)
end

function PetHatchFlow:Stop()
	if self._unsubscribe then self._unsubscribe(); self._unsubscribe = nil end
end

function PetHatchFlow:Hatch(playerId)
	return self._hatchery:Hatch(playerId)
end

return PetHatchFlow
