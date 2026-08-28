--!strict
-- Adapter for component id: ui.notification_toast.
-- Bridges normalized ui.notificationRequested events to a game-owned renderer.
-- The consumer supplies UI construction and platform-specific animation through
-- renderer:Show(payload), which may optionally return a dismiss callback.

local NotificationToastAdapter = {}
NotificationToastAdapter.__index = NotificationToastAdapter
NotificationToastAdapter.componentId = "ui.notification_toast"

export type EventBus = {
	Emit: (self: any, eventName: string, payload: any) -> (),
	Subscribe: (self: any, eventName: string, callback: (any) -> ()) -> (() -> ()),
}
export type Renderer = {
	Show: (self: any, payload: {[string]: any}) -> ((() -> ())?),
}

function NotificationToastAdapter.new(eventBus: EventBus, renderer: Renderer)
	assert(eventBus and type(eventBus.Emit) == "function" and type(eventBus.Subscribe) == "function", "NotificationToastAdapter requires EventBus.Emit and EventBus.Subscribe")
	assert(renderer and type(renderer.Show) == "function", "NotificationToastAdapter requires renderer.Show")
	return setmetatable({_eventBus=eventBus,_renderer=renderer,_unsubscribe=nil,lastNotification=nil}, NotificationToastAdapter)
end

function NotificationToastAdapter:Start()
	if self._unsubscribe then return end
	self._unsubscribe = self._eventBus:Subscribe("ui.notificationRequested", function(payload)
		assert(type(payload) == "table" and type(payload.playerId) == "number", "Notification request requires playerId")
		self.lastNotification = payload
		local dismiss = self._renderer:Show(payload)
		self._eventBus:Emit("ui.notificationShown", payload)
		if type(dismiss) == "function" then
			dismiss()
			self._eventBus:Emit("ui.notificationDismissed", payload)
		end
	end)
end

function NotificationToastAdapter:Stop()
	if self._unsubscribe then self._unsubscribe(); self._unsubscribe = nil end
end

return NotificationToastAdapter
