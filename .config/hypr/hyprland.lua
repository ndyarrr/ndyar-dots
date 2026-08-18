-- Hyprland Configuration

require("colors")

-- ◈ PASSTHRU SUBMAP

if type(hl) == "table" and type(hl.define_submap) == "function" then
    hl.define_submap("passthru", function()
        hl.bind("SUPER + SHIFT + CTRL + ALT + F35", hl.dsp.exec_cmd("true"))
    end)
elseif type(hl) == "table" and type(hl.submap) == "function" then
    hl.submap("passthru")
    hl.bind("SUPER + SHIFT + CTRL + ALT + F35", hl.dsp.exec_cmd("true"))
    hl.submap("reset")
end

-- ◈ MODULAR CONFIGURATION

require("config.variables")
require("config.monitors")
require("config.env")
require("config.autostart")
require("config.settings")
require("config.keybindings")
require("config.rules")
