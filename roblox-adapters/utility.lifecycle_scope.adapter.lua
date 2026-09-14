--!strict
--[[
	utility.lifecycle_scope — native runtime module

	Ownership container for everything a component creates that must later be
	released. Entries are disposed in reverse insertion order (LIFO), mirroring
	construction, so a child is never released after the parent that made it.

	Dispatch by tracked type:
	  RBXScriptConnection -> Disconnect()
	  Tween               -> Cancel()
	  Instance            -> Destroy()
	  thread              -> task.cancel()
	  function            -> invoked
	  LifecycleScope      -> Destroy()   (nested subtree)

	Destroy() is idempotent. Giving to an already-destroyed scope disposes the
	entry immediately instead of retaining it, so an async completion that lands
	after teardown cannot resurrect a dead view.
]]

local LifecycleScope = {}
LifecycleScope.__index = LifecycleScope

export type EventBus = {
	Emit: (self: EventBus, event: string, payload: { [string]: any }) -> (),
}

export type Config = {
	warnOnLeak: boolean?,
	maxTrackedWarn: number?,
	eventBus: EventBus?,
	id: string?,
}

type Fields = {
	_tracked: { any },
	_disposed: boolean,
	_warnOnLeak: boolean,
	_maxTrackedWarn: number,
	_eventBus: EventBus?,
	_id: string,
}

export type LifecycleScope = typeof(setmetatable({} :: Fields, LifecycleScope))

local function disposeOne(item: any): ()
	local itemType = typeof(item)

	if itemType == "RBXScriptConnection" then
		item:Disconnect()
	elseif itemType == "Instance" then
		-- Cancel is the correct release for a Tween; Destroy would also stop it
		-- but leaves the TweenService entry to be reaped on the next step.
		if item:IsA("Tween") then
			item:Cancel()
		else
			item:Destroy()
		end
	elseif itemType == "thread" then
		-- Cancelling the running thread would kill the caller mid-teardown.
		if item ~= coroutine.running() then
			pcall(task.cancel, item)
		end
	elseif itemType == "function" then
		item()
	elseif itemType == "table" and typeof(item.Destroy) == "function" then
		item:Destroy()
	end
end

function LifecycleScope.new(config: Config?): LifecycleScope
	local resolved: Config = config or {}

	return setmetatable({
		_tracked = {},
		_disposed = false,
		_warnOnLeak = if resolved.warnOnLeak == nil then true else resolved.warnOnLeak,
		_maxTrackedWarn = resolved.maxTrackedWarn or 256,
		_eventBus = resolved.eventBus,
		_id = resolved.id or "anonymous",
	} :: Fields, LifecycleScope)
end

--[[
	Track a disposable and return it unchanged, so construction can be inlined:
	    local conn = scope:Give(button.Activated:Connect(onClick))
]]
function LifecycleScope:Give<T>(item: T): T
	assert(item ~= nil, "LifecycleScope:Give expects a disposable, got nil")

	if self._disposed then
		-- Late arrival after teardown: release now rather than retain forever.
		disposeOne(item)
		return item
	end

	table.insert(self._tracked, item)

	if self._warnOnLeak and #self._tracked == self._maxTrackedWarn then
		local message = string.format(
			"[LifecycleScope:%s] tracking %d entries — likely a Give() on a repeating path that should reuse one scope",
			self._id,
			self._maxTrackedWarn
		)
		warn(message)
		if self._eventBus then
			self._eventBus:Emit("utility.scopeLeakWarning", { id = self._id, trackedCount = #self._tracked })
		end
	end

	return item
end

--[[
	Create a child scope owned by this one. Destroying the parent destroys the
	child, letting a view tear down every panel it opened in a single call.
]]
function LifecycleScope:Branch(id: string?): LifecycleScope
	local child = LifecycleScope.new({
		warnOnLeak = self._warnOnLeak,
		maxTrackedWarn = self._maxTrackedWarn,
		eventBus = self._eventBus,
		id = id or (self._id .. ".child"),
	})
	return self:Give(child)
end

--[[
	Release everything tracked so far but keep the scope usable. This is the
	call a Hide() wants: cancel the looping tweens and drop the input handlers,
	without invalidating the scope the next Show() will reuse.
]]
function LifecycleScope:Clean(): ()
	local tracked = self._tracked
	self._tracked = {}

	for index = #tracked, 1, -1 do
		local ok, err = pcall(disposeOne, tracked[index])
		if not ok then
			warn(string.format("[LifecycleScope:%s] disposal error: %s", self._id, tostring(err)))
		end
	end
end

function LifecycleScope:IsDisposed(): boolean
	return self._disposed
end

function LifecycleScope:TrackedCount(): number
	return #self._tracked
end

function LifecycleScope:Destroy(): ()
	if self._disposed then
		return
	end
	self._disposed = true

	self:Clean()

	if self._eventBus then
		self._eventBus:Emit("utility.scopeDisposed", { id = self._id })
	end
end

return LifecycleScope
