--!strict
-- Library-native implementation for component id: ui.pet_hatch_presenter
-- Converts a server-authoritative pets.hatched payload into a normalized
-- ui.notificationRequested event. Rendering remains the UI adapter's job.

local PetHatchPresenter = {}
PetHatchPresenter.__index = PetHatchPresenter
PetHatchPresenter.componentId = "ui.pet_hatch_presenter"

export type EventBus = { Emit: (self: any, eventName: string, payload: any) -> () }
export type Config = { revealSeconds: number? }
export type HatchPayload = { playerId: number, pet: { petId: string, rarity: string?, metadata: {[string]: any}? }, eggItemId: string?, hatchCost: number? }

function PetHatchPresenter.new(eventBus: EventBus, config: Config?)
	assert(eventBus and type(eventBus.Emit) == "function", "PetHatchPresenter requires EventBus.Emit")
	local revealSeconds = (config and config.revealSeconds) or 3
	assert(type(revealSeconds) == "number" and revealSeconds >= 0, "revealSeconds must be >= 0")
	return setmetatable({_eventBus=eventBus,revealSeconds=revealSeconds,lastPresentation=nil}, PetHatchPresenter)
end

function PetHatchPresenter:Present(payload: HatchPayload)
	assert(type(payload.playerId) == "number", "Hatch payload requires playerId")
	assert(payload.pet and type(payload.pet.petId) == "string" and #payload.pet.petId > 0, "Hatch payload requires pet.petId")
	local presentation = {playerId=payload.playerId,kind="pet-hatch",title="You hatched a pet!",petId=payload.pet.petId,rarity=payload.pet.rarity or "unknown",metadata=payload.pet.metadata,revealSeconds=self.revealSeconds}
	self.lastPresentation = presentation
	self._eventBus:Emit("ui.notificationRequested", presentation)
	return presentation
end

return PetHatchPresenter
