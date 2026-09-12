--!strict
--[[
	utility.remote_bootstrap — native runtime module

	Resolves a server-owned remote namespace without blocking the caller.

	The failure this replaces: a client initializer calls
	    ReplicatedStorage:WaitForChild("Game"):WaitForChild("RemoteFunctions")
	directly. When the server has not replicated yet the thread stalls; when the
	server script is missing entirely it stalls forever, and the interface hangs
	with no error raised and nothing in the output to explain it.

	Here, resolution runs on a detached thread with a per-hop timeout and the
	callback ALWAYS fires — with the remote, or with nil. "Server not ready" is
	an ordinary branch the caller handles by falling back to defaults.

	Both the container and the child-waiter are injected, so the resolver can be
	tested against a plain table tree with no DataModel present.
]]

local RemoteBootstrap = {}
RemoteBootstrap.__index = RemoteBootstrap

export type EventBus = {
	Emit: (self: EventBus, event: string, payload: { [string]: any }) -> (),
}

export type Config = {
	container: Instance | { [string]: any },
	rootName: string,
	hopTimeoutSeconds: number?,
	rootTimeoutSeconds: number?,
	eventBus: EventBus?,
	-- Injection seams for tests; both default to the Roblox implementations.
	waitForChild: ((parent: any, name: string, timeout: number) -> any?)?,
	spawn: ((fn: () -> ()) -> ())?,
}

type Fields = {
	_container: any,
	_rootName: string,
	_hopTimeout: number,
	_rootTimeout: number,
	_eventBus: EventBus?,
	_waitForChild: (parent: any, name: string, timeout: number) -> any?,
	_spawn: (fn: () -> ()) -> (),
	_cache: { [string]: any },
	_root: any,
	_rootAttempted: boolean,
	_destroyed: boolean,
}

export type RemoteBootstrap = typeof(setmetatable({} :: Fields, RemoteBootstrap))

local function defaultWaitForChild(parent: any, name: string, timeout: number): any?
	return parent:WaitForChild(name, timeout)
end

local function defaultSpawn(fn: () -> ()): ()
	task.spawn(fn)
end

function RemoteBootstrap.new(config: Config): RemoteBootstrap
	assert(config ~= nil, "RemoteBootstrap.new requires a config table")
	assert(config.container ~= nil, "RemoteBootstrap config requires a container")
	assert(typeof(config.rootName) == "string" and #config.rootName > 0,
		"RemoteBootstrap config requires a non-empty rootName")

	return setmetatable({
		_container = config.container,
		_rootName = config.rootName,
		_hopTimeout = config.hopTimeoutSeconds or 10,
		_rootTimeout = config.rootTimeoutSeconds or 15,
		_eventBus = config.eventBus,
		_waitForChild = config.waitForChild or defaultWaitForChild,
		_spawn = config.spawn or defaultSpawn,
		_cache = {},
		_root = nil,
		_rootAttempted = false,
		_destroyed = false,
	} :: Fields, RemoteBootstrap)
end

-- Walks the path on the CURRENT thread. Only ever called from inside _spawn.
function RemoteBootstrap:_resolveBlocking(path: { string }): any?
	if not self._rootAttempted then
		self._rootAttempted = true
		self._root = self._waitForChild(self._container, self._rootName, self._rootTimeout)
	end

	if self._root == nil then
		return nil
	end

	local node: any = self._root
	for _, segment in ipairs(path) do
		node = self._waitForChild(node, segment, self._hopTimeout)
		if node == nil then
			return nil
		end
	end

	return node
end

--[[
	Resolve a path beneath the root and hand it to `callback`.

	The callback is invoked exactly once, always, on a detached thread — with
	the resolved object, or nil if any hop timed out. It never runs inline, so
	callers cannot accidentally depend on synchronous completion.

	    bootstrap:Resolve({"RemoteFunctions", "GetPlayerData"}, function(remote)
	        if not remote then
	            view:ApplyDefaults()   -- server absent: a normal branch
	            return
	        end
	        ...
	    end)
]]
function RemoteBootstrap:Resolve(path: { string }, callback: (resolved: any?) -> ()): ()
	assert(typeof(path) == "table", "RemoteBootstrap:Resolve expects a path array")
	assert(typeof(callback) == "function", "RemoteBootstrap:Resolve expects a callback")

	local key = table.concat(path, "/")

	local cached = self._cache[key]
	if cached ~= nil then
		self._spawn(function()
			callback(cached)
		end)
		return
	end

	self._spawn(function()
		if self._destroyed then
			callback(nil)
			return
		end

		local resolved = self:_resolveBlocking(path)

		if self._destroyed then
			callback(nil)
			return
		end

		if resolved ~= nil then
			self._cache[key] = resolved
			if self._eventBus then
				self._eventBus:Emit("utility.remoteResolved", { path = key })
			end
		else
			if self._eventBus then
				self._eventBus:Emit("utility.remoteTimedOut", { path = key })
			end
			warn(string.format(
				"[RemoteBootstrap] '%s/%s' did not replicate within timeout — continuing on defaults",
				self._rootName,
				key
			))
		end

		callback(resolved)
	end)
end

--[[
	Cache-only lookup. Returns nil rather than waiting, for hot paths that must
	not yield (a click handler firing an already-resolved RemoteEvent).
]]
function RemoteBootstrap:Peek(path: { string }): any?
	return self._cache[table.concat(path, "/")]
end

function RemoteBootstrap:IsResolved(path: { string }): boolean
	return self._cache[table.concat(path, "/")] ~= nil
end

function RemoteBootstrap:Destroy(): ()
	self._destroyed = true
	table.clear(self._cache)
	self._root = nil
end

return RemoteBootstrap
