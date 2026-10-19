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
Player = setmetatable({}, {__index = function(_, c) return {color = c, steam_name = c .. "Player"} end})
Turns = {enable = true, turn_color = "White"}

local now = 1000.25                     -- TTS's os.time() returns fractional seconds
os.time = function() return now end

local ticks, stopped, nextWait = {}, {}, 0
Wait = {
  time = function(f, seconds, reps) nextWait = nextWait + 1; ticks[nextWait] = f; return nextWait end,
  stop = function(id) stopped[id] = true; ticks[id] = nil end,
  condition = function(f, cond) if cond() then f() end end,
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
    t.created = (t.created or 0) + 1
  end
  t.editButton = function(p) t.labels[p.index] = p.label end
  return t
end
for _, c in ipairs(CZ.seats) do timers[c] = timer(c, 7) end
timers.Purple.buttons = {}                      -- its script hasn't made its buttons yet
local others = {{getName = function() return "Life Tracker" end, getDescription = function() return "White" end}}
function getAllObjects()
  local out = {}
  for _, c in ipairs(CZ.seats) do out[#out + 1] = timers[c] end
  for _, o in ipairs(others) do out[#out + 1] = o end
  return out
end
local function label(color) return timers[color].labels[7] end

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
check(CZT.color == "White" and CZT.start == now, "a turn already running is timed from load")

-- Attaching waits for each Timer's own seven buttons, then adds ours as index 7.
tick()
for _, c in ipairs({"White", "Red", "Yellow", "Green", "Blue"}) do
  check(timers[c].created == 1 and CZT.timers[c].index == 7, c .. ": label added after the Timer's own buttons")
end
check(timers.Purple.created == nil and not CZT.attached, "a Timer without its buttons yet is left until later")
for i = 1, 7 do timers.Purple.buttons[i] = {index = i - 1, click_function = "null"} end
tick()
check(timers.Purple.created == 1 and CZT.attached, "it gets its label once its buttons exist")
tick()
check(timers.White.created == 1, "never added twice")

-- Totals accumulate across turns, shown under each seat's timer.
now = now + 125; tick()
check(label("White") == "total 2:05", "White's running total (got " .. tostring(label("White")) .. ")")
onPlayerTurn({color = "Red"}, {color = "White"})
check(CZT.total.White == 125 and CZT.color == "Red", "White's turn is banked when Red starts")
now = now + 30; tick()
check(label("White") == "total 2:05" and label("Red") == "total 0:30", "both totals shown")
check(label("Green") == nil or label("Green") == "", "a seat that hasn't played shows nothing")
onPlayerTurn({color = "White"}, {color = "Red"})
now = now + 60; tick()
check(label("White") == "total 3:05", "White's total keeps adding up across turns (got " .. tostring(label("White")) .. ")")

-- The announcer: once at 5 minutes, once at 10, for this turn only.
now = now + 238; tick()                                  -- 4:58 into the turn
check(#played == 0, "nothing before 5 minutes")
now = now + 2; tick()                                    -- 5:00
check(played[1] == "test://tts/sounds/slow-5min.wav", "5-minute clip plays (got " .. tostring(played[1]) .. ")")
check(broadcasts[#broadcasts]:find("WHAT'S TAKING SO LONG", 1, true) and broadcasts[#broadcasts]:find("WhitePlayer", 1, true),
  "5-minute line broadcast with the player's name")
now = now + 30; tick(); tick()
check(#played == 1, "the 5-minute line plays once")
now = now + 270; tick()                                  -- 10:00
check(played[2] == "test://tts/sounds/slow-10min.wav", "10-minute clip plays")
check(broadcasts[#broadcasts]:find("WAKE ME UP", 1, true), "10-minute line broadcast")
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

-- Rolling the "Who goes first?" die starts a new game; other shuffles don't.
local deck = {getName = function() return "Deck" end, getDescription = function() return "" end}
onObjectRandomize(deck, "White")
check(CZT.total.White and CZT.total.White > 0, "shuffling a deck doesn't reset")
local die = {getName = function() return "Who goes first?" end,
             getDescription = function() return "Who goes first dice [scripted] by 0rganics, v2.5" end}
Turns.turn_color = "Green"
onObjectRandomize(die, "White")
check(next(CZT.total) == nil, "the die roll resets every total")
check(label("White") == "" and label("Red") == "", "totals cleared from the timers")
check(CZT.color == "Green" and CZT.start == now, "the current turn is timed from the roll")
local rolled = {getName = function() return "goes first!" end, getDescription = function() return "" end}
now = now + 10; tick()
onObjectRandomize(rolled, "White")
check(next(CZT.total) == nil and CZT.start == now, "the die after a roll is recognised too")

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

print(string.format("%d checks, %d failed", checks, failures))
os.exit(failures == 0 and 0 or 1)
