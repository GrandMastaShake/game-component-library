--!strict
return function()
	local EggHatchery = require(script.Parent.Parent.EggHatchery)
	local function bus() local e={}; return {events=e,Emit=function(_,n,p)table.insert(e,{name=n,payload=p})end} end
	local function inventory(eggs) local c={StarterEgg=eggs}; return {counts=c,HasItem=function(_,_,id,q)return(c[id]or 0)>=q end,RemoveItem=function(_,_,id,q)if(c[id]or 0)<q then return false end;c[id]-=q;return true end,AddItem=function(_,_,id,q)c[id]=(c[id]or 0)+q;return true end} end
	it("selects deterministic weighted result and emits pets.hatched",function()
		local b=bus(); local i=inventory(1); local h=EggHatchery.new(b,{inventory=i,random={NextNumber=function()return 0.05 end}},{eggItemId="StarterEgg",hatchTable={{petId="CommonPup",rarity="common",weight=80},{petId="MoonFox",rarity="rare",weight=20}}})
		local result,err=h:Hatch(123); expect(err).to.equal(nil); expect(result.petId).to.equal("CommonPup"); expect(i.counts.StarterEgg).to.equal(0); expect(i.counts.CommonPup).to.equal(1); expect(b.events[#b.events].name).to.equal("pets.hatched")
	end)
	it("rejects missing egg",function()
		local b=bus(); local h=EggHatchery.new(b,{inventory=inventory(0),random={NextNumber=function()return 0 end}},{eggItemId="StarterEgg",hatchTable={{petId="CommonPup",weight=1}}}); local result,err=h:Hatch(123); expect(result).to.equal(nil); expect(err).to.equal("missing-egg")
	end)
end
