-- The salamander as two halves, joined at the waist (tools/anim/rig.py draws them: bank "chattysalamander", the front
-- half - head, forelegs, chest - and "chattysalamander_rear", the back half - hips, hind legs, tail). The creature
-- itself is the front half: it walks, thinks and is what is clicked and hit; its origin is the waist. The back half
-- follows it like a snake (its hips pulled after the waist, a rope's length behind), drawn by each player's own game
-- as a piece attached at the waist - so the join never opens however it bends - drawn at the bend the hips have. The mouse on the back half is the mouse on the creature (client_forward_target). On the
-- server two invisible bodies, at the chest and at the hips, give it the shape the drawing has: what players and
-- creatures bump into. A hit landing nearer the hips flinches the back half only.
local M = {}

M.HIP = 1.2            -- (world units from the waist to the middle of the hips (the 3D model's hind legs: 2.03 of its
--                         units, 68.75 build px each, 117 build px a world unit), and to the middle of the chest)
M.CHEST = 1.3
M.RADIUS = 1.0         -- (the chest's and the hips' bodies)
M.BEND = 50            -- (degrees the back half bends at most: past it the hips are dragged round)
M.TURN_RATE = 240      -- (degrees a second the creature turns at most: it never snaps round, so neither do its hips -
--                         the hitbox at the hips sweeps round with the drawing instead of jumping; the user, 2026-11-05:
--                         "I don't want instances where the hitbox suddenly teleports")

-- (the animations, as rig.py's ANIMS: their lengths and whether they loop - the back half plays the front's)
local ANIMS = {
    idle = true, idle_look = false, walk_pre = false, walk_loop = true, walk_pst = false, talk = true, think = true,
    happy = false, sad = false, surprised = false, angry = false, dance = false, eat = false, attack = false,
    hit = false, death = false, sleep_pre = false, sleep_loop = true, sleep_pst = false,
}

local function wrap(a)
    while a > 180 do a = a - 360 end
    while a < -180 do a = a + 360 end
    return a
end

-- (a heading in degrees, as the game's Transform rotation has it, as a vector on the ground: forward is (cos, -sin))
local function dir(deg)
    local r = math.rad(deg)
    return math.cos(r), -math.sin(r)
end

-- the hips dragged after the waist: st holds them (hx, hz); the back half's heading and its bend from the front's
function M.trail(inst, st)
    local x, _, z = inst.Transform:GetWorldPosition()
    local rot = inst.Transform:GetRotation()
    if st.hx == nil then
        local fx, fz = dir(rot)
        st.hx, st.hz = x - fx * M.HIP, z - fz * M.HIP
    end
    local dx, dz = x - st.hx, z - st.hz
    local d = math.sqrt(dx * dx + dz * dz)
    local heading = d > 1e-4 and math.deg(math.atan2(-dz, dx)) or rot
    local bend = wrap(heading - rot)
    if bend > M.BEND then bend = M.BEND elseif bend < -M.BEND then bend = -M.BEND end
    heading = rot + bend
    local hx, hz = dir(heading)
    st.hx, st.hz = x - hx * M.HIP, z - hz * M.HIP
    st.heading, st.bend = heading, bend
    return st
end

function M.chest(inst)
    local x, _, z = inst.Transform:GetWorldPosition()
    local fx, fz = dir(inst.Transform:GetRotation())
    return x + fx * M.CHEST, z + fz * M.CHEST
end

-- (server) where the tail is: its middle, behind the hips along the back half's heading; and that heading
M.TAIL = 1.3           -- (world units from the hips to the tail's middle)
function M.tailPos(inst)
    local st = M.trail(inst, inst.chattybody)
    local hx, hz = dir(st.heading)
    return st.hx - hx * M.TAIL, st.hz - hz * M.TAIL, st.heading
end

-- which half a hit from attacker lands on: "rear" if it is nearer the hips than the chest
function M.hitSide(inst, attacker)
    local st = inst.chattybody
    if not (st and st.hx and attacker and attacker:IsValid()) then return "front" end
    local ax, _, az = attacker.Transform:GetWorldPosition()
    local cx, cz = M.chest(inst)
    local dc = (ax - cx) ^ 2 + (az - cz) ^ 2
    local dh = (ax - st.hx) ^ 2 + (az - st.hz) ^ 2
    return dh < dc and "rear" or "front"
end

-- --- the client: the back half's piece -----------------------------------------------------------------------------

-- (the back half is drawn at BINS bends (tools/blender/sal_render.py: rendered from the 3D model, the body curving
--  over the waist like a snake's): it plays "<anim>_b<bin>", the bend nearest its own. The drawings' bend is the 3D
--  model's: + the hips swung to the creature's right. The game's st.bend is + with the hips to its left (its rotation
--  turns clockwise seen from above); the side view facing left is the right-facing one mirrored, so there the other)
M.BINS = {-50, -37.5, -25, -12.5, 0, 12.5, 25, 37.5, 50}
-- (the heading each view is drawn for, camera-relative (rotation less the camera's heading): right, up, left, down)
local VIEW_REL = {[0] = 180, [1] = 90, [2] = 0, [3] = -90}
M.BIN_STEP = 12.5

function M.bin(bend, facing)
    local b = (facing == 2) and bend or -bend
    local i = math.floor((b - M.BINS[1]) / M.BIN_STEP + 0.5)
    return math.max(0, math.min(#M.BINS - 1, i))
end

-- (its drawings: a build for each view (the game draws two atlases of a build at most, and the back half at every
--  bend is more) - its piece takes the one for the view it shows)
local BUILDS = {[0] = "chattysalamander_rear_side", [2] = "chattysalamander_rear_side",
    [3] = "chattysalamander_rear_down", [1] = "chattysalamander_rear_up"}
M.REAR_BUILDS = {"chattysalamander_rear_side", "chattysalamander_rear_down", "chattysalamander_rear_up"}

-- (the tail dropped: the back half's stump drawings, its tail hidden)
local STUMP = {bodyr = "bodyrs", fhips = "fhipss", bhips = "bhipss"}
local TAILS = {"tail", "ftail", "btail"}

local function setStump(rear, on)
    rear.tailless = on
    for sym, stump in pairs(STUMP) do
        if on then rear.AnimState:OverrideSymbol(sym, rear.build, stump)
        else rear.AnimState:ClearOverrideSymbol(sym) end
    end
    for _, t in ipairs(TAILS) do
        if on then rear.AnimState:HideSymbol(t) else rear.AnimState:ShowSymbol(t) end
    end
end

local function syncRear(inst)
    local rear = inst.chattyrear
    if not (rear and rear:IsValid()) then return end
    local st = M.trail(inst, inst.chattyrearst)
    local facing = inst.AnimState:GetCurrentFacing()          -- (0 right, 1 up, 2 left, 3 down)
    local build = BUILDS[facing] or BUILDS[0]
    local tailless = inst.chattytailless:value()
    if build ~= rear.build then
        rear.build = build
        rear.AnimState:SetBuild(build)
        if tailless then setStump(rear, true) end
    end
    if tailless ~= (rear.tailless or false) then setStump(rear, tailless) end
    -- (going away, the back half is nearer us: over the front; else under it)
    rear.AnimState:SetFinalOffset(facing == 1 and 1 or -1)
    -- (its animation: the front's, at the same time, at its bend - but its own flinch when hit there)
    local now = GetTime()
    -- (the bend it is drawn at: where the hips really are against the heading this view is drawn for (straight
    --  right, up, left, down the screen) - not against the front's own heading - so the drawn hips stay over the
    --  hips' body however the front is turned within its view)
    local cam = TheCamera and TheCamera:GetHeading() or 0
    local bin = M.bin(wrap(st.heading - cam - VIEW_REL[facing]), facing)
    if rear.flinchUntil and now < rear.flinchUntil then
        if bin ~= rear.bin and rear.anim == "hit" then
            local t = rear.AnimState:GetCurrentAnimationTime()
            rear.AnimState:PlayAnimation("hit_b" .. bin)
            rear.AnimState:SetTime(t)
            rear.bin = bin
        end
        return
    end
    local name
    for n in pairs(ANIMS) do
        if inst.AnimState:IsCurrentAnimation(n) then name = n break end
    end
    if name == nil then return end
    local t = inst.AnimState:GetCurrentAnimationTime()
    if name == "hit" then name, t = "idle", now end
    if rear.anim ~= name or rear.bin ~= bin then
        rear.AnimState:PlayAnimation(name .. "_b" .. bin, ANIMS[name])
        rear.anim, rear.bin = name, bin
    end
    local len = rear.AnimState:GetCurrentAnimationLength()
    if ANIMS[name] and len > 0 then t = t % len elseif len > 0 then t = math.min(t, len) end
    rear.AnimState:SetTime(t)
end

local function onRearHit(inst)
    local rear = inst.chattyrear
    if not (rear and rear:IsValid()) then return end
    rear.AnimState:PlayAnimation("hit_b" .. (rear.bin or 4))
    rear.anim = "hit"
    rear.flinchUntil = GetTime() + rear.AnimState:GetCurrentAnimationLength()
end

-- (the prefab's common part, on the server and every client)
function M.common(inst)
    inst.chattyrearhit = net_event(inst.GUID, "chattysalamander.rearhit")
    inst.chattytailless = net_bool(inst.GUID, "chattysalamander.tailless", "chattysalamander.taillessdirty")
    if TheNet:IsDedicated() then return end
    local rear = CreateEntity()
    --[[Non-networked entity]]
    rear.entity:SetCanSleep(TheWorld.ismastersim)
    rear.persists = false
    rear.entity:AddTransform()
    rear.entity:AddAnimState()
    rear.Transform:SetFourFaced()
    rear.AnimState:SetBank("chattysalamander_rear")
    rear.build = BUILDS[0]
    rear.AnimState:SetBuild(rear.build)
    rear.AnimState:PlayAnimation("idle_b4", true)
    rear.anim, rear.bin = "idle", 4
    rear.entity:SetParent(inst.entity)
    rear.client_forward_target = inst           -- (the mouse on it is the mouse on the salamander)
    inst.chattyrear = rear
    inst.highlightchildren = {rear}
    inst.chattyrearst = {}
    inst:DoPeriodicTask(0, syncRear)
    inst:ListenForEvent("chattysalamander.rearhit", onRearHit)
end

-- --- the server: its turning, the bodies at the chest and the hips ------------------------------------------------

local function turnTowards(inst, want)
    inst.chattywant = want
end

local function turnStep(inst)
    local want = inst.chattywant
    if want == nil then return end
    local now = GetTime()
    local dt = math.min(now - (inst.chattyturnT or now), 0.1)
    inst.chattyturnT = now
    local rot = inst.Transform:GetRotation()
    local d = wrap(want - rot)
    local step = M.TURN_RATE * dt
    if math.abs(d) <= step then
        inst.Transform:SetRotation(want)
        inst.chattywant = nil
    else
        inst.Transform:SetRotation(rot + (d > 0 and step or -step))
    end
end

-- (its facing goes through turnTowards: the entity's own FacePoint / ForceFacePoint and its locomotor's SetMoveDir)
local function limitTurning(inst)
    local function toward(x, z)
        local px, _, pz = inst.Transform:GetWorldPosition()
        if math.abs(x - px) + math.abs(z - pz) < 1e-3 then return end
        turnTowards(inst, math.deg(math.atan2(-(z - pz), x - px)))
    end
    function inst:FacePoint(x, y, z)
        if type(x) == "table" then x, z = x.x, x.z end
        toward(x, z)
    end
    inst.ForceFacePoint = inst.FacePoint
    local loco = inst.components.locomotor
    if loco then
        function loco:SetMoveDir(dir) turnTowards(inst, dir) end
    end
    inst.chattyturnT = GetTime()
    inst:DoPeriodicTask(0, turnStep)
end

local function placeBodies(inst)
    local st = M.trail(inst, inst.chattybody)
    local chest, hips = inst.chattyblocks and inst.chattyblocks[1], inst.chattyblocks and inst.chattyblocks[2]
    if chest and chest:IsValid() then
        local cx, cz = M.chest(inst)
        chest.Physics:Teleport(cx, 0, cz)
    end
    if hips and hips:IsValid() then hips.Physics:Teleport(st.hx, 0, st.hz) end
end

local function removeBodies(inst)
    for _, b in ipairs(inst.chattyblocks or {}) do
        if b:IsValid() then b:Remove() end
    end
    inst.chattyblocks = nil
end

function M.master(inst)
    inst.chattybody = {}
    limitTurning(inst)
    inst:DoTaskInTime(0, function()
        if inst.components.health and inst.components.health:IsDead() then return end
        inst.chattyblocks = {SpawnPrefab("chattysalamander_block"), SpawnPrefab("chattysalamander_block")}
        placeBodies(inst)
    end)
    inst:DoPeriodicTask(0, placeBodies)
    inst:ListenForEvent("death", removeBodies)
    inst:ListenForEvent("onremove", removeBodies)
    -- (the hips: hit there, the back half flinches - the front goes on)
    function inst.chattyRearHit()
        inst.chattyrearhit:push()
        if not TheNet:IsDedicated() then onRearHit(inst) end
    end
end

-- (debug, client) rings on the ground where its three bodies are - the waist (its own), the chest, the hips - to see
-- them against the drawing: c_salamanderhitboxes(true)
function M.showBodies(inst, on)
    for _, m in ipairs(inst.chattymarks or {}) do if m:IsValid() then m:Remove() end end
    inst.chattymarks = nil
    if inst.chattymarktask then inst.chattymarktask:Cancel() inst.chattymarktask = nil end
    if not on then return end
    inst.chattymarks = {}
    for i = 1, 3 do
        local m = SpawnPrefab("reticule")
        m.Transform:SetScale(1.6, 1.6, 1.6)                 -- (about the bodies' size)
        m.AnimState:SetLayer(LAYER_WORLD)                   -- (over the creature, see-through)
        m.AnimState:SetFinalOffset(3)
        m.AnimState:SetMultColour(1, i == 3 and 0.3 or 1, i == 1 and 1 or 0.3, 0.8)
        inst.chattymarks[i] = m
    end
    inst.chattymarktask = inst:DoPeriodicTask(0, function()
        local x, _, z = inst.Transform:GetWorldPosition()
        local cx, cz = M.chest(inst)
        local st = inst.chattybody and inst.chattybody.hx and inst.chattybody or M.trail(inst, inst.chattyrearst)
        local at = {{x, z}, {cx, cz}, {st.hx, st.hz}}
        for i, m in ipairs(inst.chattymarks) do
            if m:IsValid() then m.Transform:SetPosition(at[i][1], 0, at[i][2]) end
        end
    end)
end

-- the invisible body the chest and the hips each have: players and creatures bump into it; it does not stop the
-- salamander itself (the creature's own body - at the waist - is not in its group)
function M.blockfn()
    local inst = CreateEntity()
    inst.entity:AddTransform()
    inst.entity:AddNetwork()
    local phys = inst.entity:AddPhysics()
    phys:SetMass(99999)
    phys:SetFriction(0)
    phys:SetDamping(5)
    phys:SetCollisionGroup(COLLISION.GIANTS)
    phys:ClearCollisionMask()
    phys:CollidesWith(COLLISION.CHARACTERS)
    phys:SetCapsule(M.RADIUS, 2)
    inst:AddTag("NOCLICK")
    inst:AddTag("NOBLOCK")
    inst:AddTag("notarget")
    inst.entity:SetPristine()
    if not TheWorld.ismastersim then return inst end
    inst.persists = false
    return inst
end

return M
