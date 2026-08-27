--!strict
-- Adapter for component.schema.json id: world.terrain_generator
-- Wraps roblox-modular-lib/src/TerrainGenerator.lua (depends on world.noise_lib)
-- NOTE: real TerrainGenerator.lua API not yet verified; TODOs mark unverified calls.

local Adapter = {}
Adapter.componentId = "world.terrain_generator"

export type TerrainConfig = {
	regionSize: number?,
	maxHeight: number?,
}

-- Inputs (per schema): regionSize (default 512), maxHeight (default 100)
-- Outputs (per schema): heightmap (array), isGenerated (boolean)
-- Emits: world.terrainGenerated
-- Dependencies (per schema): world.noise_lib
function Adapter.new(noiseLibAdapter: any, config: TerrainConfig?)
	local cfg = config or {}
	local self = {
		_noiseLib = noiseLibAdapter,
		_regionSize = cfg.regionSize or 512,
		_maxHeight = cfg.maxHeight or 100,
		heightmap = {},
		isGenerated = false,
	}

	-- TODO: require the real TerrainGenerator module and pass the noise
	-- sampler from the noise_lib adapter into it, e.g.:
	-- local Terrain = require(RobloxModularLib.TerrainGenerator)
	-- self.heightmap = Terrain.generate(self._regionSize, self._maxHeight, noiseLibAdapter.sample2D)

	return self
end

return Adapter
