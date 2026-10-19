--[[ ======================================================================
  Cactuar turn totals and the slow-turn announcer: appended to the table's
  Global script after cactuar.lua by scripts/build_tts_table.py.

  The table's six "Timer" objects show how long the current turn has taken.
  Under each one this adds the seat's total across every turn of the game,
  and when one turn reaches 5 and then 10 minutes, an announcer mocks the
  player: a big broadcast, and a voice clip through the music player so the
  whole table hears it (tts/sounds/). Rolling the "Who goes first?" die
  starts a new game and resets the totals.

  The table's own scripts are left alone: the Timer objects keep their seven
  buttons (ours is added after them, so their indexes don't move), and the
  Global events used here are wrapped, not replaced.

  Chat: "announcer off" / "announcer on" / "announcer test".
====================================================================== ]]

-- Loading this again (a live patch) keeps the game's totals and stops the old ticker.
local cztPrevious = CZT
if cztPrevious and cztPrevious.ticker then pcall(function() Wait.stop(cztPrevious.ticker) end) end

CZT = {
  total = {},          -- seat colour -> seconds banked this game
  color = nil,         -- whose turn is running
  start = nil,         -- os.time() when it began
  announced = {},      -- thresholds already announced this turn
  timers = {},         -- seat colour -> {obj = Timer object, index = our button}
  muted = false,
  lines = {
    {at = 300, text = "C'mon bro, what's taking so long?", sound = "sounds/slow-5min.wav"},
    {at = 600, text = "Bruh, wake me up when you're done.", sound = "sounds/slow-10min.wav"},
  },
}

local CZT_TIMER_BUTTONS = 7      -- the Timer script's own buttons, indexes 0-6

local function cztSeat(color)
  for _, c in ipairs(CZ.seats) do
    if c == color then return true end
  end
  return false
end

local function cztElapsed()
  if not CZT.color or not CZT.start then return 0 end
  return math.max(0, math.floor(os.time() - CZT.start))   -- TTS's os.time() has fractions
end

local function cztTotal(color)
  return (CZT.total[color] or 0) + (color == CZT.color and cztElapsed() or 0)
end

local function cztClock(seconds)
  local h, m, s = math.floor(seconds / 3600), math.floor(seconds / 60) % 60, seconds % 60
  if h > 0 then return string.format("%d:%02d:%02d", h, m, s) end
  return string.format("%d:%02d", m, s)
end

function cztNoop() end

-- Add our label under each Timer once its own seven buttons exist, so their
-- editButton indexes stay valid. Returns true when every seat has one.
local function cztAttach()
  local done = 0
  for _, obj in ipairs(getAllObjects()) do
    local color = obj.getName() == "Timer" and obj.getDescription() or nil
    if color and cztSeat(color) then
      local buttons = obj.getButtons() or {}
      local index = nil   -- explicit: TTS's MoonSharp can leave a bare `local` holding a stale value in loops
      for _, b in ipairs(buttons) do
        if b.click_function == "cztNoop" then index = b.index end
      end
      if not index and #buttons >= CZT_TIMER_BUTTONS then
        local c, n = Color.fromString(color), #buttons      -- ours becomes index n
        obj.createButton({
          click_function = "cztNoop", function_owner = Global, label = "",
          position = {0, 1, 0.95}, width = 0, height = 0, font_size = 240,
          color = {0, 0, 0, 0}, font_color = {c.r, c.g, c.b, 0.85},
          tooltip = "Total time on turns this game",
        })
        index = n
      end
      if index then
        CZT.timers[color] = {obj = obj, index = index}
        done = done + 1
      end
    end
  end
  return done >= #CZ.seats
end

local function cztShow(color)
  local t = CZT.timers[color]
  if not t or t.obj == nil then return end
  local total = cztTotal(color)
  local label = (CZT.hidden or total == 0) and "" or ("total " .. cztClock(total))
  pcall(function() t.obj.editButton({index = t.index, label = label}) end)
end

local function cztShowAll()
  for _, c in ipairs(CZ.seats) do cztShow(c) end
end

local function cztAnnounce(line, color)
  local who = Player[color] and Player[color].steam_name or color
  broadcastToAll(string.upper(line.text) .. "  (" .. who .. ")", {1, 0.45, 0.2})
  if CZT.muted then return end
  pcall(function()
    -- soundBase: set by hand to test clips from somewhere other than CZ.base.
    MusicPlayer.setCurrentAudioclip({url = (CZT.soundBase or CZ.base) .. line.sound, title = "Announcer: " .. line.text})
    Wait.condition(function() MusicPlayer.play() end, function() return MusicPlayer.loaded end, 15)
  end)
end

-- Bank the finished turn and start timing the next one.
function cztSwitch(color)
  if CZT.color then
    CZT.total[CZT.color] = cztTotal(CZT.color)
    local finished = CZT.color
    CZT.color, CZT.start = nil, nil
    cztShow(finished)
  end
  if color and cztSeat(color) then
    CZT.color, CZT.start, CZT.announced = color, os.time(), {}
  end
  cztShow(color)
end

-- A new game: forget every total, and time the current turn from now.
function cztReset()
  CZT.total, CZT.announced = {}, {}
  CZT.color, CZT.start = nil, nil
  if Turns.enable and cztSeat(Turns.turn_color) then
    CZT.color, CZT.start = Turns.turn_color, os.time()
  end
  cztShowAll()
end

function cztTick()
  if not CZT.attached then CZT.attached = cztAttach() end
  if not CZT.color then return end
  cztShow(CZT.color)
  local elapsed = cztElapsed()
  for i, line in ipairs(CZT.lines) do
    if elapsed >= line.at and not CZT.announced[i] then
      CZT.announced[i] = true
      cztAnnounce(line, CZT.color)
    end
  end
end

local function cztIsStartDie(obj)
  local name, desc = obj.getName() or "", obj.getDescription() or ""
  return name == "Who goes first?" or name == "goes first!" or desc:find("Who goes first", 1, true) ~= nil
end

-- ---------- Global events, wrapped so any existing handler still runs ----------
-- Captured once: a live patch re-running this file must not wrap its own wrappers.
CZT_BASE = CZT_BASE or {turn = onPlayerTurn, randomize = onObjectRandomize, chat = onChat}

function onPlayerTurn(player, previous)
  cztSwitch(player and player.color)
  if CZT_BASE.turn then return CZT_BASE.turn(player, previous) end
end

function onObjectRandomize(obj, color)
  if obj and cztIsStartDie(obj) then
    cztReset()
    broadcastToAll("New game: turn totals reset.", {0.6, 0.9, 0.6})
  end
  if CZT_BASE.randomize then return CZT_BASE.randomize(obj, color) end
end

function onChat(message, player)
  local m = string.lower(message or "")
  if m == "announcer off" then CZT.muted = true; broadcastToAll("Announcer muted.", {0.7, 0.7, 0.7})
  elseif m == "announcer on" then CZT.muted = false; broadcastToAll("Announcer on.", {0.7, 0.7, 0.7})
  elseif m == "announcer test" then cztAnnounce(CZT.lines[1], player and player.color or "White")
  elseif m == "timers off" then CZT.hidden = true; cztShowAll()
  elseif m == "timers on" then CZT.hidden = false; cztShowAll()
  end
  if CZT_BASE.chat then return CZT_BASE.chat(message, player) end
end

-- Start ticking once loaded. A turn already running when the script loads is
-- timed from now, unless a live patch carries the running turn over.
if cztPrevious then
  CZT.total, CZT.color, CZT.start = cztPrevious.total or {}, cztPrevious.color, cztPrevious.start
  CZT.announced, CZT.muted, CZT.hidden = cztPrevious.announced or {}, cztPrevious.muted, cztPrevious.hidden
  CZT.soundBase = cztPrevious.soundBase
elseif Turns and Turns.enable and cztSeat(Turns.turn_color) then
  CZT.color, CZT.start = Turns.turn_color, os.time()
end
CZT.ticker = Wait.time(cztTick, 1, -1)
