name = "Gummy the Slime (AI companion)"
author = "McPuppetFace"
version = "0.1.1"
api_version = 10
dst_compatible = true
all_clients_require_mod = true
client_only_mod = false
priority = -10
icon_atlas = "modicon.xml"
icon = "modicon.tex"
server_filter_tags = {"creature", "companion", "ai"}

description = [[Gummy, a little slime, lives near the portal. Talk to it and it answers, follows you, comes when called, stays, carries messages to other players, and shows how it feels: happy, sad, surprised, angry, a dance, a nap. Give it food, or ask it to eat what lies on the ground. When something attacks you or it, it decides for itself whether to fight or flee (only the host can order an attack). It notices dusk, rain and danger, gets bored, and chats with other chatty creatures.

It talks through Proximity Comms (needed) and an admin's free Koetama app with a large language model (an AI service the admin chooses). Without one the slime still hops about and blubs.

Tell your players: what is said near the slime goes to that AI service.]]

-- (Proximity Comms: the Workshop item, or a copy in the mods folder named proxcomms)
mod_dependencies = {
    {workshop = "workshop-3819346216", ["proxcomms"] = false},
}

configuration_options =
{
    {
        name = "count",
        label = "Slimes",
        hover = "How many slimes live near the portal.",
        options = {
            {description = "0", data = 0}, {description = "1", data = 1}, {description = "2", data = 2},
            {description = "3", data = 3}, {description = "5", data = 5},
        },
        default = 1,
    },
    {
        name = "hears",
        label = "It listens to",
        hover = "What a slime hears without a Koetama that scores (0.5.14 or later; with one, it hears everything near it and answers what concerns it): lines with its name (and the talk that follows), or everything said near it.",
        options = {
            {description = "Its name", data = "engaged", hover = "Say its name first; it keeps listening to you for 30 s."},
            {description = "Everything near", data = "near", hover = "Every line said near it goes to the AI."},
        },
        default = "engaged",
    },
    {
        name = "greet",
        label = "Greets players",
        hover = "It says hello when a player comes near (at most every 10 minutes each).",
        options = {{description = "On", data = true}, {description = "Off", data = false}},
        default = true,
    },
    {
        name = "chatter",
        label = "Talks with others",
        hover = "It hears the other chatty creatures (slimes, salamanders) and they talk among themselves, up to this many lines in a row. Each line is a request to the admin's AI.",
        options = {
            {description = "Off", data = 0}, {description = "4 lines", data = 4}, {description = "10 lines", data = 10},
            {description = "20 lines", data = 20},
        },
        default = 10,
    },
    {
        name = "respawn_days",
        label = "Comes back after",
        hover = "A slime that died: a new one appears near the portal after this many days.",
        options = {
            {description = "Never", data = 0}, {description = "1 day", data = 1}, {description = "3 days", data = 3},
            {description = "10 days", data = 10},
        },
        default = 3,
    },
}
