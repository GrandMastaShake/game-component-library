--!strict
return function()
	local PetHatchPresenter = require(script.Parent.Parent.PetHatchPresenter)
	it("normalizes a hatch payload and emits ui.notificationRequested", function()
		local events = {}
		local bus = {Emit=function(_, name, payload) table.insert(events,{name=name,payload=payload}) end}
		local presenter = PetHatchPresenter.new(bus,{revealSeconds=2.5})
		local presentation = presenter:Present({playerId=123,pet={petId="MoonFox",rarity="rare",metadata={variant="lunar"}}})
		expect(presentation.kind).to.equal("pet-hatch")
		expect(presentation.petId).to.equal("MoonFox")
		expect(presentation.rarity).to.equal("rare")
		expect(presentation.revealSeconds).to.equal(2.5)
		expect(events[1].name).to.equal("ui.notificationRequested")
		expect(events[1].payload.petId).to.equal("MoonFox")
	end)
end
