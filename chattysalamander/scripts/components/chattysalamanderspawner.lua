-- (the forest's master) the host's number of salamanders, by the pond nearest the portal (by the portal, if there is
-- no pond): the first time the world runs with the mod, and again a few days after one died
local cfg = require "chattysalamander/config"

local POND = {"pond", "pond_mos", "pond_cave"}
local POND_NEAR = 200          -- (a pond further from the portal than this: by the portal instead)

local Spawner = Class(function(self, inst)
    self.inst = inst
    self.salamanders = {}
    self.started = false
    self.deaths = {}                  -- the days salamanders died on, waiting to come back
    inst:DoTaskInTime(3, function() self:Start() end)
    inst:WatchWorldState("cycles", function() self:Respawn() end)
end)

function Spawner:Track(s)
    if self.salamanders[s] then return end
    self.salamanders[s] = true
    s:ListenForEvent("onremove", function() self.salamanders[s] = nil end)
    s:ListenForEvent("death", function()
        self.deaths[#self.deaths + 1] = TheWorld.state.cycles
    end)
end

function Spawner:Count()
    local n = 0
    for s in pairs(self.salamanders) do
        if s:IsValid() and not (s.components.health and s.components.health:IsDead()) then n = n + 1 end
    end
    return n
end

local function portal()
    return TheSim:FindFirstEntityWithTag("multiplayer_portal")
end

-- the pond nearest the portal (or the portal)
function Spawner:Home()
    local p = portal()
    if not p then return nil end
    local best, bd
    for _, e in pairs(Ents) do
        if e.prefab and e:IsValid() then
            for _, name in ipairs(POND) do
                if e.prefab == name then
                    local d = e:GetDistanceSqToInst(p)
                    if d < POND_NEAR * POND_NEAR and (not bd or d < bd) then best, bd = e, d end
                end
            end
        end
    end
    return best or p, best ~= nil
end

function Spawner:SpawnOne()
    local where, pond = self:Home()
    if not where then return nil end
    local pos = where:GetPosition()
    local off = FindWalkableOffset(pos, math.random() * 2 * PI, (pond and 4 or 7) + math.random() * 3, 12, true, false)
    if off then pos = pos + off end
    local s = SpawnPrefab("chattysalamander")
    s.Transform:SetPosition(pos:Get())
    s.components.knownlocations:RememberLocation("home", pos)
    return s
end

function Spawner:Start()
    if self.started then return end
    self.started = true
    for _ = 1, cfg.count - self:Count() do self:SpawnOne() end
end

function Spawner:Respawn()
    if cfg.respawn_days <= 0 then return end
    local today = TheWorld.state.cycles
    local keep = {}
    for _, day in ipairs(self.deaths) do
        if today - day >= cfg.respawn_days and self:Count() < cfg.count then
            self:SpawnOne()
        else
            keep[#keep + 1] = day
        end
    end
    self.deaths = keep
end

function Spawner:OnSave()
    return {started = self.started, deaths = self.deaths}
end

function Spawner:OnLoad(data)
    if data then
        self.started = data.started == true
        self.deaths = type(data.deaths) == "table" and data.deaths or {}
    end
end

return Spawner
