-- Plays tts/cactuar_turns.lua (turn totals and the slow-turn announcer) against
-- stand-ins for Tabletop Simulator. Run from the repo root:
--     lua tests/test_cactuar_turns.lua
-- tests/test_cactuar_lua.py runs it as part of the suite when lua is installed.

local failures, checks = 0, 0
local function check(cond, what)
  checks = checks + 1
  if not cond then
    failures = failures + 1
    print("FAIL: " .. what)
  end
end

local function read(path)
  local f = assert(io.open(path, "rb"))
  local text = f:read("a"); f:close()
  return text
end

-- ---------- stand-ins ----------
CZ = {base = "test://tts/", seats = {"White", "Red", "Yellow", "Green", "Blue", "Purple"}}
Global = {}
Color = {fromString = function() return {r = 1, g = 0.5, b = 0} end}
Player = setmetatable({Yellow = {color = "Yellow", steam_name = "YellowPlayer", seated = true}},
  {__index = function(_, c) return {color = c, steam_name = c .. "Player"} end})
-- Enough JSON for the save round trip (TTS provides the real one).
local function ser(v)
  if type(v) == "table" then
    local parts = {}
    for k, x in pairs(v) do parts[#parts + 1] = "[" .. string.format("%q", k) .. "]=" .. ser(x) end
    return "{" .. table.concat(parts, ",") .. "}"
  end
  return type(v) == "string" and string.format("%q", v) or tostring(v)
end
JSON = {encode = ser, decode = function(text) return assert(load("return " .. text))() end}

local now = 1000.25                     -- TTS's os.time() returns fractional seconds
os.time = function() return now end

local ticks, stopped, nextWait = {}, {}, 0
Wait = {
  time = function(f, seconds, reps) nextWait = nextWait + 1; ticks[nextWait] = f; return nextWait end,
  stop = function(id) stopped[id] = true; ticks[id] = nil end,
  condition = function(f, cond) if cond() then f() end end,
  frames = function(f) f() end,
}
local function tick()
  for id, f in pairs(ticks) do f() end
end

local played, broadcasts = {}, {}
MusicPlayer = {loaded = true,
  setCurrentAudioclip = function(p) played[#played + 1] = p.url end,
  play = function() end}
function broadcastToAll(msg) broadcasts[#broadcasts + 1] = msg end

-- Six Timer objects, each starting with the table script's seven buttons.
local timers = {}
local function timer(color, ownButtons)
  local t = {color = color, buttons = {}, labels = {}}
  for i = 1, ownButtons do t.buttons[i] = {index = i - 1, click_function = "null"} end
  t.getName = function() return "Timer" end
  t.getDescription = function() return color end
  t.getButtons = function() return t.buttons end
  t.createButton = function(p)
    t.buttons[#t.buttons + 1] = {index = #t.buttons, click_function = p.click_function}
    t.fontColor = p.font_color
    t.created = (t.created or 0) + 1
  end
  t.editButton = function(p)
    if p.label ~= nil then t.labels[p.index] = p.label end
    if p.font_size then t.fonts = t.fonts or {}; t.fonts[p.index] = p.font_size end
  end
  -- The Timer script's own state: its clock starts on onPlayerTurn, which also counts a turn.
  t.vars = {turnN = 0}                              -- a fresh table: no turns played
  t.calls = {}
  t.getVar = function(k) return t.vars[k] end
  t.setVar = function(k, v) t.vars[k] = v end
  t.call = function(fn, arg)
    t.calls[#t.calls + 1] = fn
    if fn == "onPlayerTurn" and arg and arg.color == color then
      t.vars.timerID = 1
      t.vars.turnN = t.vars.turnN + 1
      t.labels[6] = t.vars.turnN
    end
  end
  return t
end
for _, c in ipairs(CZ.seats) do timers[c] = timer(c, 7) end
timers.Purple.buttons = {}                      -- its script hasn't made its buttons yet
-- Red already has a label from an older version of this script (smaller font).
timers.Red.buttons[8] = {index = 7, click_function = "cztNoop"}
timers.Red.vars.timerID = 99                    -- and its own clock is somehow running
-- Turns: setting turn_color fires onPlayerTurn on Global and on every object, as TTS does.
local turnsRaw = {enable = true, turn_color = "White"}
Turns = setmetatable({}, {__index = turnsRaw, __newindex = function(_, k, v)
  local old = turnsRaw[k]
  turnsRaw[k] = v
  if k == "turn_color" and v ~= old then
    for _, c in ipairs(CZ.seats) do timers[c].call("onPlayerTurn", {color = v}) end
    if onPlayerTurn then onPlayerTurn({color = v}, {color = old}) end
  end
end})
-- The "Who goes first?" die: its faces are seated players' names or empty seats' colours.
local dieValue = nil
local function dieNamed(name)
  return {getName = function() return name end,
          getDescription = function() return name == "Who goes first?" and "Who goes first dice [scripted] by 0rganics, v2.5" or "" end,
          getRotationValue = function() return dieValue end, resting = true}
end
local others = {{getName = function() return "Life Tracker" end, getDescription = function() return "White" end}}
function getAllObjects()
  local out = {}
  for _, c in ipairs(CZ.seats) do out[#out + 1] = timers[c] end
  for _, o in ipairs(others) do out[#out + 1] = o end
  return out
end
local function label(color) return timers[color].labels[7] end
-- The Cactuar tile whose memo holds the state (rewinds keep object fields, not script data).
local tile = {memo = nil}
function getObjectFromGUID(guid) if guid == "c4c7a1" then return tile end return nil end
-- A saved game: what a load or rewind finds (the tile's memo; Global's script data too).
local function setSaved(state) tile.memo = state; Global.script_state = state end

-- The table's own chat handler must keep working.
local baseChats = 0
function onChat() baseChats = baseChats + 1 end

-- ---------- load ----------
local source = read("tts/cactuar_turns.lua")
-- TTS's MoonSharp doesn't reset a bare `local x` inside a loop (it kept getAllObjects()'s
-- list in a live game), so every local in these scripts starts with a value.
for _, path in ipairs({"tts/cactuar.lua", "tts/cactuar_turns.lua", "tts/cactuar_tile.lua"}) do
  local n = 0
  for line in read(path):gmatch("[^\n]+") do
    n = n + 1
    check(not line:match("^%s*local%s+[%w_,%s]+$"), path .. ":" .. n .. " declares a local without a value")
  end
end
assert(load(source, "cactuar_turns.lua"))()
check(not CZT.started and CZT.color == nil, "a fresh game waits: nothing is timed at load")

-- Attaching waits for each Timer's own seven buttons, then adds ours as index 7.
tick()
for _, c in ipairs({"White", "Yellow", "Green", "Blue"}) do
  check(timers[c].created == 1 and CZT.timers[c].index == 7, c .. ": label added after the Timer's own buttons")
end
check(timers.Red.created == nil and CZT.timers.Red.index == 7, "an existing label is reused, not duplicated")
check(timers.Red.fonts and timers.Red.fonts[7] == 320, "an existing label is restyled to the current size")
check(timers.Purple.created == nil and not CZT.attached, "a Timer without its buttons yet is left until later")
check(timers.White.fontColor and timers.White.fontColor[4] == 100,
  "the label uses alpha 100 like the Timer's own labels: TTS doesn't draw an alpha of 1 here")
for i = 1, 7 do timers.Purple.buttons[i] = {index = i - 1, click_function = "null"} end
tick()
check(timers.Purple.created == 1 and CZT.attached, "it gets its label once its buttons exist")
check(timers.White.vars.timerID == nil, "the table's clock isn't started before the roll")
check(timers.White.vars.timerOn == false and timers.Green.vars.timerOn == false,
  "the table's own clocks are kept quiet before the roll")
onPlayerTurn({color = "Red"}, {color = "White"})                -- fired while the table loads
check(not CZT.started and CZT.color == nil, "a turn event while the table loads doesn't start the game")
now = now + 100; tick()
check(next(CZT.total) == nil and (label("Red") or "") == "", "nothing timed before the first turn")
check((label("Yellow") or "") == "", "no totals on the table before the first turn")

-- The die's script rebuilding itself (no player) or a "roll" right after load starts nothing.
local resumeAt = now
local rebuilt = dieNamed("Who goes first?")
dieValue = "WhitePlayer"
onObjectRandomize(rebuilt, nil)
check(not CZT.started, "the die rebuilding itself (no player) doesn't start the game")
onObjectRandomize(rebuilt, "Grey")
check(not CZT.started, "a spectator's roll doesn't start the game")
now = CZT.loadedAt + 3
onObjectRandomize(rebuilt, "White")
check(not CZT.started, "nothing in the first seconds after load counts as a roll")
now = resumeAt

-- The first player's turn starts the game: turn 1, timers running.
timers.Blue.vars.turnN = 4                                      -- turns passed during setup
onPlayerTurn({color = "Blue"}, {color = "Red"})
check(CZT.started and CZT.color == "Blue" and CZT.start == now, "the first player's turn starts the timers")
check(timers.Blue.vars.turnN == 1 and timers.Blue.labels[6] == 1, "it is turn 1 on the table clock")
check(timers.Blue.vars.timerID ~= nil and timers.Blue.vars.timerOn == true, "the table clock runs")
check(timers.Green.vars.turnN == 0 and timers.Green.vars.timerOn == true, "every other seat starts from 0")
check(broadcasts[#broadcasts]:find("BluePlayer takes the first turn", 1, true), "the table is told")
now = now + 30; tick()
check(label("Blue") == "total 0:30", "Blue's total runs (got " .. tostring(label("Blue")) .. ")")
onPlayerTurn({color = "Red"}, {color = "Blue"})
check(CZT.color == "Red" and CZT.total.Blue == 30, "later turns just switch, they don't restart the game")

-- Rolling the die starts a new game. Here it lands on White, whose turn it already is.
local die = dieNamed("Who goes first?")
dieValue = "WhitePlayer"
onObjectRandomize(die, "White")
check(CZT.started and CZT.color == "White" and CZT.start == now, "the roll starts turn 1 for the player it picked")
check(timers.White.vars.turnN == 1 and timers.White.vars.timerID ~= nil, "the table's clock starts at turn 1")
check(timers.Green.vars.turnN == 0 and timers.Green.vars.timerOn == true, "every seat's counter zeroed, clocks enabled")
check(broadcasts[#broadcasts]:find("WhitePlayer goes first. Turn 1.", 1, true), "the table is told who goes first")
tick()
check(timers.White.created == 1, "never added twice")

-- Totals accumulate across turns, shown under each seat's timer.
now = now + 125; tick()
check(label("White") == "total 2:05", "White's running total (got " .. tostring(label("White")) .. ")")
onPlayerTurn({color = "Red"}, {color = "White"})
check(CZT.total.White == 125 and CZT.color == "Red", "White's turn is banked when Red starts")
now = now + 30; tick()
check(label("White") == "total 2:05" and label("Red") == "total 0:30", "both totals shown")
check(label("Green") == nil or label("Green") == "", "an empty seat that hasn't played shows nothing")
for _ = 1, 5 do tick() end
check(label("Yellow") == "total 0:00", "a seated player's total shows from 0:00 (got " .. tostring(label("Yellow")) .. ")")
onPlayerTurn({color = "White"}, {color = "Red"})
now = now + 60; tick()
check(label("White") == "total 3:05", "White's total keeps adding up across turns (got " .. tostring(label("White")) .. ")")

-- The announcer: once at 5 minutes, once at 10, for this turn only.
now = now + 238; tick()                                  -- 4:58 into the turn
check(#played == 0, "nothing before 5 minutes")
now = now + 2; tick()                                    -- 5:00
check(played[1] == "test://tts/sounds/slow-5min.wav", "5-minute clip plays (got " .. tostring(played[1]) .. ")")
check(broadcasts[#broadcasts]:find("YO TWIN, HURRY YO ASS UP", 1, true) and broadcasts[#broadcasts]:find("WhitePlayer", 1, true),
  "5-minute line broadcast with the player's name")
now = now + 30; tick(); tick()
check(#played == 1, "the 5-minute line plays once")
now = now + 270; tick()                                  -- 10:00
check(played[2] == "test://tts/sounds/slow-10min.wav", "10-minute clip plays")
check(broadcasts[#broadcasts]:find("IN THE BENINGING", 1, true), "10-minute line broadcast")
now = now + 3000; tick()
check(#played == 2, "nothing more after 10 minutes")
check(label("White") == "total 1:02:05", "hours shown once a total passes an hour (got " .. tostring(label("White")) .. ")")

-- A new turn re-arms the announcer.
onPlayerTurn({color = "Red"}, {color = "White"})
now = now + 300; tick()
check(played[3] == "test://tts/sounds/slow-5min.wav", "the next slow turn is announced too")

-- Muting stops the voice but keeps the broadcast; the table's chat handler still runs.
local chatsBefore = baseChats
onChat("Announcer Off", {color = "White"})
check(CZT.muted and baseChats == chatsBefore + 1, "announcer off, and the table's onChat still ran")
onPlayerTurn({color = "Yellow"}, {color = "Red"})
local shown = #broadcasts
now = now + 300; tick()
check(#played == 3 and #broadcasts > shown, "muted: broadcast only")
onChat("announcer on", {color = "White"})
onChat("announcer test", {color = "Blue"})
check(played[4] == "test://tts/sounds/slow-5min.wav" and broadcasts[#broadcasts]:find("BluePlayer", 1, true), "announcer test plays the clip")
onChat("timers off", {color = "White"})
check(label("White") == "", "timers off hides the totals")
onChat("timers on", {color = "White"})
check(label("White") ~= "", "timers on shows them again")

-- Rolling the die again starts a new game; other shuffles don't.
local deck = {getName = function() return "Deck" end, getDescription = function() return "" end}
onObjectRandomize(deck, "White")
check(CZT.total.White and CZT.total.White > 0, "shuffling a deck doesn't reset")
dieValue = "Green"                                   -- an empty seat's face shows its colour
onObjectRandomize(die, "White")
check(CZT.total.White == nil and CZT.total.Red == nil, "the die roll resets every total")
check(label("White") == "" and label("Red") == "", "totals cleared from the timers")
check(Turns.turn_color == "Green" and CZT.color == "Green" and CZT.start == now, "the turn passes to the picked seat")
check(timers.Green.vars.turnN == 1, "and its table clock shows turn 1")
-- A "Roll again" face starts nothing.
local rolled = dieNamed("goes first!")
dieValue = "Roll again to see who"
now = now + 10; tick()
onObjectRandomize(rolled, "White")
check(not CZT.started and CZT.color == nil, "a Roll again face starts nothing")
check(broadcasts[#broadcasts]:find("Roll the die again", 1, true), "and says so")
dieValue = "GreenPlayer"
onObjectRandomize(rolled, "White")
check(CZT.started and CZT.color == "Green" and CZT.start == now, "the rolled die is recognised by name, by Steam name")

-- The totals go into the save and come back on a fresh load, until a reset.
now = now + 20; tick()
local saved = onSave()
local decoded = JSON.decode(saved).cactuar_turn_totals
check(decoded and decoded.Green and decoded.Green > 0, "the save holds the totals, running turn included")
check(JSON.decode(saved).cactuar_started == true, "the save records that the game has started")
local liveCZT, liveBase = CZT, CZT_BASE
CZT = nil
setSaved(saved)
assert(load(source, "cactuar_turns.lua"))()
for id, f in pairs(ticks) do if id == CZT.ticker then f() end end      -- attach: the saved state is read now
local running = JSON.decode(saved).cactuar_turn
check(running and running.color == "Green" and running.elapsed == 20, "the save holds the running turn and its time")
check(CZT.started and CZT.color == "Green" and CZT.start == now - 20, "a reloaded (rewound) game continues the running turn")
check(CZT.total.Green + (now - CZT.start) == decoded.Green, "and the total counts that turn once, not twice")
for id, f in pairs(ticks) do if id == CZT.ticker then f() end end      -- attach
check(timers.Green.vars.tdiff == 20, "the table's own turn clock picks up at 0:20, not 0:00")
Wait.stop(CZT.ticker)                    -- that simulated reload's ticker
CZT = nil
setSaved(JSON.encode({cactuar_started = false, cactuar_turn_totals = {Green = 5}}))
assert(load(source, "cactuar_turns.lua"))()
for id, f in pairs(ticks) do if id == CZT.ticker then f() end end      -- attach: the saved state is read now
check(not CZT.started and CZT.color == nil and next(CZT.total) == nil, "a saved game nobody rolled for still waits")
Wait.stop(CZT.ticker)
-- "timers on" resumes a waiting game (a rewind) from the current turn, without a roll.
CZT = nil
setSaved(JSON.encode({cactuar_started = false, cactuar_turn_totals = {}}))
for _, c in ipairs(CZ.seats) do timers[c].vars.timerOn = false; timers[c].vars.timerID = nil end
timers.Blue.vars.turnN = 6
turnsRaw.turn_color = "Blue"
assert(load(source, "cactuar_turns.lua"))()
for id, f in pairs(ticks) do if id == CZT.ticker then f() end end      -- attach
check(not CZT.started and timers.Blue.vars.timerOn == false, "a rewound game waits")
onChat("timers on", {color = "White"})
check(CZT.started and CZT.color == "Blue" and CZT.start == now, "timers on resumes from the current turn")
check(timers.Blue.vars.timerOn == true and timers.Blue.vars.timerID ~= nil, "the current player's clock runs again")
check(timers.Blue.vars.turnN == 6, "turn numbers are kept, not restarted at 1")
check(broadcasts[#broadcasts]:find("resumed", 1, true), "the table is told")
local before = CZT.start
now = now + 5
onChat("timers on", {color = "White"})
check(CZT.start == before, "a second timers on changes nothing")
Wait.stop(CZT.ticker)
turnsRaw.turn_color = "Green"
-- Rewind snapshots don't call onSave: the state is kept in Global.script_state as
-- turns change, so a snapshot taken mid-game has it.
check(Global.script_state and JSON.decode(Global.script_state).cactuar_started == true,
  "the started flag is written to Global's state without a save")
-- After a load or rewind this script runs before the objects exist: the tile holding the
-- state can't be found yet. The state must be read at attach, not at load.
local liveTile = tile
CZT = nil
setSaved(JSON.encode({cactuar_started = true, cactuar_turn_totals = {White = 90}}))
Global.script_state = ""                                   -- a rewind empties script data
getObjectFromGUID = function() return nil end              -- objects not loaded yet
assert(load(source, "cactuar_turns.lua"))()
check(not CZT.started, "nothing is decided before the objects exist")
getObjectFromGUID = function(guid) if guid == "c4c7a1" then return liveTile end return nil end
for id, f in pairs(ticks) do if id == CZT.ticker then f() end end
check(CZT.started and CZT.total.White == 90, "the tile's state is restored once it exists")
Wait.stop(CZT.ticker)

-- A snapshot with no state of ours, but table clocks that counted turns, resumes
-- instead of restarting the game at turn 1.
CZT = nil
setSaved("")
for _, c in ipairs(CZ.seats) do timers[c].vars.timerOn = false; timers[c].vars.timerID = nil; timers[c].vars.turnN = 0 end
timers.Red.vars.turnN = 7
turnsRaw.turn_color = "Red"
assert(load(source, "cactuar_turns.lua"))()
for id, f in pairs(ticks) do if id == CZT.ticker then f() end end      -- attach
check(CZT.started and CZT.color == "Red", "a game in progress without our state resumes at attach")
check(timers.Red.vars.turnN == 7, "keeping its turn number")
Wait.stop(CZT.ticker)
-- And a fresh table (every clock at 0) with no state waits for the first turn.
CZT = nil
setSaved("")
timers.Red.vars.turnN = 0
assert(load(source, "cactuar_turns.lua"))()
for id, f in pairs(ticks) do if id == CZT.ticker then f() end end
check(not CZT.started, "a fresh table waits for the first turn")
Wait.stop(CZT.ticker)
turnsRaw.turn_color = "Green"

-- A started game whose table clocks were switched off (a script reset, "timers off")
-- gets them back on when it attaches, with the running clock's turn number shown.
for _, c in ipairs(CZ.seats) do timers[c].vars.timerOn = false; timers[c].labels[5] = nil end
timers.Green.vars.timerID = 7
CZT = nil
setSaved(JSON.encode({cactuar_started = true, cactuar_turn_totals = {}}))
assert(load(source, "cactuar_turns.lua"))()
local t2 = nil
for id, f in pairs(ticks) do if id == CZT.ticker then t2 = f end end
t2()
check(timers.White.vars.timerOn == true and timers.Green.vars.timerOn == true, "a started game switches the table clocks back on")
check(timers.Green.labels[5] == "turn" and timers.Green.labels[6] == timers.Green.vars.turnN, "and shows the running clock's turn number")
Wait.stop(CZT.ticker)
setSaved("not json")
CZT = nil
assert(load(source, "cactuar_turns.lua"))()
for id, f in pairs(ticks) do if id == CZT.ticker then f() end end      -- attach: the saved state is read now
check(next(CZT.total) == nil, "an unreadable save starts from nothing")
Wait.stop(CZT.ticker)
CZT = liveCZT
setSaved(nil)

-- A live patch (the script loaded again) keeps the game and doesn't double up.
now = now + 50; tick()
onPlayerTurn({color = "Blue"}, {color = "Green"})
local greenTotal, oldTicker = CZT.total.Green, CZT.ticker
assert(load(source, "cactuar_turns.lua"))()
check(stopped[oldTicker], "the old ticker is stopped")
check(CZT.total.Green == greenTotal and CZT.color == "Blue", "totals and the running turn survive")
chatsBefore = baseChats
onChat("hello", {color = "White"})
check(baseChats == chatsBefore + 1, "the table's onChat runs once, not wrapped twice")
local live = 0
for _ in pairs(ticks) do live = live + 1 end
check(live == 1, "one ticker running (" .. live .. ")")

-- The Pirate Cannon (patched by build_tts_table.fix_cannon_script) hands the die's
-- winner to cztStartGame. After a load the winner often already holds the turn, so no
-- turn event fires: the game must still start, with turn 1 on their clock.
tick()                                           -- the ticker attaches the clocks
CZT.started = false
for _, c in ipairs(CZ.seats) do timers[c].vars.timerID = nil; timers[c].labels = {} end
turnsRaw.turn_color = "Blue"                     -- set raw: TTS fires nothing for an unchanged turn
cztStartGame("Blue")
check(CZT.started and CZT.color == "Blue", "the cannon's pick starts the game on the current turn")
check(timers.Blue.labels[5] == "turn" and timers.Blue.labels[6] == 1, "turn 1 shows on the winner's clock (got " .. tostring(timers.Blue.labels[6]) .. ")")
check(timers.Blue.vars.turnN == 1 and timers.Blue.vars.timerID ~= nil, "their clock is running, counted once")
-- A different winner: the turn moves, and their clock shows turn 1 too.
timers.Green.vars.timerID = nil
cztStartGame("Green")
check(turnsRaw.turn_color == "Green" and CZT.color == "Green", "the turn moves to the cannon's pick")
check(timers.Green.labels[6] == 1 and timers.Green.vars.turnN == 1, "turn 1 on the new winner's clock, not 2")
check(read("scripts/build_tts_table.py"):find("cztStartGame", 1, true), "the build patches the cannon to call cztStartGame")

print(string.format("%d checks, %d failed", checks, failures))
os.exit(failures == 0 and 0 or 1)
