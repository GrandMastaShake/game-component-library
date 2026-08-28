--!strict
return function()
	local PetHatchFlow = require(script.Parent.Parent.PetHatchFlow)
	it("hatches, requests a presentation, and marks persistence dirty", function()
		local listeners, events, dirtyCalls = {}, {}, {}
		local bus = {
			Emit=function(_,name,payload) table.insert(events,{name=name,payload=payload}); if listeners[name] then listeners[name](payload) end end,
			Subscribe=function(_,name,callback) listeners[name]=callback; return function() listeners[name]=nil end end,
		}
		local counts={StarterEgg=1}
		local inventory={
			HasItem=function(_,_,id,quantity)return(counts[id]or 0)>=quantity end,
			RemoveItem=function(_,_,id,quantity)counts[id]-=quantity;return true end,
			AddItem=function(_,_,id,quantity)counts[id]=(counts[id]or 0)+quantity;return true end,
		}
		local flow=PetHatchFlow.new(bus,{inventory=inventory,random={NextNumber=function()return 0 end},markPersistenceDirty=function(playerId,payload)table.insert(dirtyCalls,{playerId=playerId,petId=payload.pet.petId})end},{eggItemId="StarterEgg",hatchTable={{petId="MoonFox",rarity="rare",weight=1}},revealSeconds=1})
		flow:Start()
		local result,err=flow:Hatch(42)
		expect(err).to.equal(nil)
		expect(result.petId).to.equal("MoonFox")
		expect(counts.StarterEgg).to.equal(0)
		expect(counts.MoonFox).to.equal(1)
		expect(events[1].name).to.equal("ui.notificationRequested")
		expect(events[1].payload.petId).to.equal("MoonFox")
		expect(dirtyCalls[1].playerId).to.equal(42)
		flow:Stop()
	end)
end
