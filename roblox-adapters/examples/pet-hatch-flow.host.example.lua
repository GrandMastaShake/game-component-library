--!strict
-- Server composition example. Require paths are illustrative; inject modules
-- according to the consuming project's Rojo/Wally/Studio layout.

local EventBus = require(UpstreamModules.EventBus)
local PetHatchFlow = require(GameComponentLibrary.PetHatchFlow)
local eventBus = EventBus.new()

local flow = PetHatchFlow.new(eventBus, {
	inventory = authoritativeInventory,
	currency = authoritativeCurrency,
	random = Random.new(),
	markPersistenceDirty = function(playerId, hatchPayload)
		persistenceService:MarkDirty(playerId, "pet-hatch", hatchPayload)
	end,
}, {
	eggItemId = "StarterEgg", hatchCost = 0, revealSeconds = 3,
	hatchTable = {{petId="CommonPup",rarity="common",weight=80},{petId="MoonFox",rarity="rare",weight=20}},
})
flow:Start()

-- Bind only on the server. Derive identity from transport, never client input.
-- HatchRequest.OnServerInvoke = function(player) return flow:Hatch(player.UserId) end
