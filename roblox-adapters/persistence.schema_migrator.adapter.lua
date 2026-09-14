--!strict
--[[
	persistence.schema_migrator — native runtime module

	Reconciles a loaded save payload against the current default shape.

	persistence.datastore_safe guarantees the bytes arrive. This guarantees they
	have the right shape: a player returning after a release that added
	`Stats.CompetitionsWon` reads 0, not nil, without every call site growing a
	nil-guard that then never gets removed.

	Merge rules:
	  - saved scalar over default scalar   -> saved wins
	  - key absent from saved              -> default fills in
	  - table over table                   -> recurse
	  - array over array                   -> saved replaces wholesale
	  - type mismatch (saved 5, default {}) -> default wins, mismatch reported

	Arrays replace rather than merge because index-wise merging on an owned
	inventory is never what the caller means: a player who sold down from five
	items to three must not have items 4 and 5 resurrected from defaults.

	Pure table transform — no platform services, fully deterministic.
]]

local SchemaMigrator = {}
SchemaMigrator.__index = SchemaMigrator

export type Migration = {
	toVersion: number,
	migrate: (payload: { [string]: any }) -> { [string]: any },
	note: string?,
}

export type EventBus = {
	Emit: (self: EventBus, event: string, payload: { [string]: any }) -> (),
}

export type Config = {
	currentVersion: number,
	migrations: { Migration }?,
	pruneUnknownKeys: boolean?,
	versionKey: string?,
	eventBus: EventBus?,
}

export type Report = {
	didMigrate: boolean,
	migratedFrom: number,
	migratedTo: number,
	appliedMigrations: { number },
	typeMismatches: { string },
	prunedKeys: { string },
}

type Fields = {
	_currentVersion: number,
	_migrations: { Migration },
	_prune: boolean,
	_versionKey: string,
	_eventBus: EventBus?,
}

export type SchemaMigrator = typeof(setmetatable({} :: Fields, SchemaMigrator))

local function isArray(value: { [any]: any }): boolean
	if next(value) == nil then
		return false -- empty table: treat as a record so defaults can populate it
	end
	local count = 0
	for key in pairs(value) do
		if typeof(key) ~= "number" then
			return false
		end
		count += 1
	end
	return count == #value
end

local function deepCopy(value: any): any
	if typeof(value) ~= "table" then
		return value
	end
	local copy = {}
	for key, inner in pairs(value) do
		copy[key] = deepCopy(inner)
	end
	return copy
end

function SchemaMigrator.new(config: Config): SchemaMigrator
	assert(config ~= nil, "SchemaMigrator.new requires a config table")
	assert(typeof(config.currentVersion) == "number",
		"SchemaMigrator config requires a numeric currentVersion")

	local migrations = config.migrations or {}
	table.sort(migrations, function(a: Migration, b: Migration): boolean
		return a.toVersion < b.toVersion
	end)

	return setmetatable({
		_currentVersion = config.currentVersion,
		_migrations = migrations,
		_prune = config.pruneUnknownKeys or false,
		_versionKey = config.versionKey or "__schemaVersion",
		_eventBus = config.eventBus,
	} :: Fields, SchemaMigrator)
end

function SchemaMigrator:_merge(
	saved: { [string]: any },
	defaults: { [string]: any },
	path: string,
	report: Report
): { [string]: any }
	local result: { [string]: any } = {}

	for key, defaultValue in pairs(defaults) do
		local savedValue = saved[key]
		local here = if path == "" then tostring(key) else path .. "." .. tostring(key)

		if savedValue == nil then
			result[key] = deepCopy(defaultValue)
		elseif typeof(defaultValue) == "table" and typeof(savedValue) == "table" then
			if isArray(defaultValue) or isArray(savedValue) then
				result[key] = deepCopy(savedValue)
			else
				result[key] = self:_merge(savedValue, defaultValue, here, report)
			end
		elseif typeof(defaultValue) ~= typeof(savedValue) then
			-- Corrupt or hand-edited payload: the default is the trustworthy shape.
			table.insert(report.typeMismatches, string.format(
				"%s (saved %s, expected %s)", here, typeof(savedValue), typeof(defaultValue)
			))
			result[key] = deepCopy(defaultValue)
		else
			result[key] = savedValue
		end
	end

	if not self._prune then
		for key, savedValue in pairs(saved) do
			if result[key] == nil then
				result[key] = deepCopy(savedValue)
			end
		end
	else
		for key in pairs(saved) do
			if defaults[key] == nil and key ~= self._versionKey then
				local here = if path == "" then tostring(key) else path .. "." .. tostring(key)
				table.insert(report.prunedKeys, here)
			end
		end
	end

	return result
end

--[[
	Bring `saved` up to the current schema against a freshly built `defaults`.
	Returns the reconciled payload and a report describing what changed.

	    local data, report = migrator:Apply(loadedFromStore, buildDefaults(player))
	    if report.didMigrate then saveSystem:MarkDirty(player) end
]]
function SchemaMigrator:Apply(
	saved: { [string]: any }?,
	defaults: { [string]: any }
): ({ [string]: any }, Report)
	assert(typeof(defaults) == "table", "SchemaMigrator:Apply requires a defaults table")

	local report: Report = {
		didMigrate = false,
		migratedFrom = self._currentVersion,
		migratedTo = self._currentVersion,
		appliedMigrations = {},
		typeMismatches = {},
		prunedKeys = {},
	}

	-- No prior save: defaults are already correct and current.
	if saved == nil or typeof(saved) ~= "table" or next(saved) == nil then
		local fresh = deepCopy(defaults)
		fresh[self._versionKey] = self._currentVersion
		return fresh, report
	end

	local savedVersion = tonumber(saved[self._versionKey]) or 0
	report.migratedFrom = savedVersion

	local working: { [string]: any } = deepCopy(saved)

	-- Ordered version migrations for shape changes a merge cannot express
	-- (a renamed key, a scalar promoted to a table).
	for _, migration in ipairs(self._migrations) do
		if migration.toVersion > savedVersion and migration.toVersion <= self._currentVersion then
			local ok, migrated = pcall(migration.migrate, working)
			if ok and typeof(migrated) == "table" then
				working = migrated
				table.insert(report.appliedMigrations, migration.toVersion)
				report.didMigrate = true
			else
				if self._eventBus then
					self._eventBus:Emit("persistence.schemaMigrationFailed", {
						toVersion = migration.toVersion,
						error = tostring(migrated),
					})
				end
				warn(string.format(
					"[SchemaMigrator] migration to v%d failed: %s",
					migration.toVersion,
					tostring(migrated)
				))
			end
		end
	end

	local result = self:_merge(working, defaults, "", report)
	result[self._versionKey] = self._currentVersion
	report.migratedTo = self._currentVersion

	if savedVersion ~= self._currentVersion then
		report.didMigrate = true
	end

	if report.didMigrate and self._eventBus then
		self._eventBus:Emit("persistence.schemaMigrated", {
			from = report.migratedFrom,
			to = report.migratedTo,
			applied = report.appliedMigrations,
		})
	end

	return result, report
end

return SchemaMigrator
