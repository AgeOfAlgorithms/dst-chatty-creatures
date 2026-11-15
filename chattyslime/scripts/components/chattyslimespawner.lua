-- (the forest's master) the host's number of slimes, near the portal: the first time the world runs with the mod,
-- and again a few days after one died
local cfg = require "chattyslime/config"

local Spawner = Class(function(self, inst)
    self.inst = inst
    self.slimes = {}
    self.started = false
    self.deaths = {}                  -- the days slimes died on, waiting to come back
    inst:DoTaskInTime(3, function() self:Start() end)
    inst:WatchWorldState("cycles", function() self:Respawn() end)
end)

function Spawner:Track(slime)
    if self.slimes[slime] then return end
    self.slimes[slime] = true
    slime:ListenForEvent("onremove", function() self.slimes[slime] = nil end)
    slime:ListenForEvent("death", function()
        self.deaths[#self.deaths + 1] = TheWorld.state.cycles
    end)
end

function Spawner:Count()
    local n = 0
    for s in pairs(self.slimes) do
        if s:IsValid() and not (s.components.health and s.components.health:IsDead()) then n = n + 1 end
    end
    return n
end

local function portal()
    return TheSim:FindFirstEntityWithTag("multiplayer_portal")
end

function Spawner:SpawnOne()
    local p = portal()
    if not p then return nil end
    local pos = p:GetPosition()
    local off = FindWalkableOffset(pos, math.random() * 2 * PI, 6 + math.random() * 4, 12, true, false)
    if off then pos = pos + off end
    local s = SpawnPrefab("chattyslime")
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
