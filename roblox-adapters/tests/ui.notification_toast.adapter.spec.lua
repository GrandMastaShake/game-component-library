--!strict
return function()
	local NotificationToastAdapter = require(script.Parent.Parent["ui.notification_toast.adapter"])
	it("renders notification requests and emits lifecycle events", function()
		local listeners, emitted, rendered = {}, {}, {}
		local bus = {
			Emit=function(_,name,payload)table.insert(emitted,{name=name,payload=payload})end,
			Subscribe=function(_,name,callback) listeners[name]=callback; return function() listeners[name]=nil end end,
		}
		local adapter = NotificationToastAdapter.new(bus,{Show=function(_,payload)table.insert(rendered,payload);return function() end end})
		adapter:Start()
		listeners["ui.notificationRequested"]({playerId=7,kind="pet-hatch",petId="MoonFox"})
		expect(rendered[1].petId).to.equal("MoonFox")
		expect(emitted[1].name).to.equal("ui.notificationShown")
		expect(emitted[2].name).to.equal("ui.notificationDismissed")
		adapter:Stop()
		expect(listeners["ui.notificationRequested"]).to.equal(nil)
	end)
end
