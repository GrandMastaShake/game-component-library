--!strict
-- Adapter for component.schema.json id: movement.basic_walk
-- Wraps the real locomotion API so it matches the Lego contract's inputs/outputs/events.
-- TODO: verify exact function signatures against roblox-modular-lib/src/init.lua exports
-- once that module is pulled in as a dependency of this repo (e.g. via Wally).

local Adapter = {}
Adapter.componentId = "movement.basic_walk"

export type WalkConfig = {
	walkSpeed: number?,
	acceleration: number?,
}

-- Constructs a component instance bound to a character/humanoid.
-- Inputs (per schema): walkSpeed (default 16), acceleration (default 8)
-- Outputs (per schema): isMoving (boolean), velocity (Vector3)
-- Emits: movement.started, movement.stopped
-- ListensTo: input.moveDirection
function Adapter.new(character: Model, config: WalkConfig?)
	local cfg = config or {}
	local walkSpeed = cfg.walkSpeed or 16
	local acceleration = cfg.acceleration or 8

	local humanoid = character:FindFirstChildOfClass("Humanoid")
	assert(humanoid, "movement.basic_walk adapter requires a Humanoid on the character")
	humanoid.WalkSpeed = walkSpeed

	local self = {
		_humanoid = humanoid,
		_acceleration = acceleration,
		isMoving = false,
		velocity = Vector3.zero,
		_emitters = {}, -- populated by the EventBus in the real module
	}

	-- Real wiring: connect to Humanoid.Running / Humanoid.MoveDirection changes
	-- and forward movement.started / movement.stopped through the shared EventBus
	-- from roblox-modular-lib's Core module once that dependency is added here.

	return self
end

return Adapter
