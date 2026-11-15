-- the host's settings (modmain fills them in)
return {
    hears = "engaged",        -- engaged: say its name first / near: everything said near it
    greet = true,             -- it says hello when a player comes near (an event for its language model)
    chatter = 10,             -- it hears other chatty creatures, up to this many lines in a row (0: never)
    count = 1,                -- slimes near the portal
    respawn_days = 3,         -- a slime that died comes back after this many days (0: never)
}
