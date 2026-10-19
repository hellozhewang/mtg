--[[ ======================================================================
  Cactuar turn totals and the slow-turn announcer: appended to the table's
  Global script after cactuar.lua by scripts/build_tts_table.py.

  The table's six "Timer" objects show how long the current turn has taken.
  Under each one this adds the seat's total across every turn of the game,
  and when one turn reaches 5 and then 10 minutes, an announcer mocks the
  player: a big broadcast, and a voice clip through the music player so the
  whole table hears it (tts/sounds/).

  Nothing runs until the first seated player's turn begins: that turn is turn
  1 and the totals start. Rolling the "Who goes first?" die starts a new game
  the same way, for the player it lands on. The totals stay on the table,
  every seated player's, kept in the save, until the next new game. A loaded
  or rewound game that is waiting resumes with "timers on".

  The table's own scripts are left alone: the Timer objects keep their seven
  buttons (ours is added after them, so their indexes don't move), and the
  Global events used here are wrapped, not replaced.

  Chat: "announcer off" / "announcer on" / "announcer test"; "timers off" /
  "timers on" hide and show the totals, and "timers on" also resumes a game
  that is waiting (after a rewind or a mid-game load) without a die roll.
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
-- Alpha 100, as the Timer's own labels use: a label on these Timer blocks with an
-- ordinary alpha (1, or 0.85) is not drawn at all (seen in game, 2026-10-18).
local CZT_LABEL = {position = {0, 1, 0.95}, font_size = 320, alpha = 100}

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

-- The game's state as saved: whether it started, every seat's total (running
-- turn included) and every seat's turn number on the table's own clocks.
local function cztState()
  local totals, turns = {}, {}
  for _, c in ipairs(CZ.seats) do
    local t = cztTotal(c)
    if t > 0 then totals[c] = t end
    local timer = CZT.timers[c]
    if timer then
      pcall(function() turns[c] = tonumber(timer.obj.getVar("turnN")) or 0 end)
    end
  end
  local running = CZT.color and {color = CZT.color, elapsed = cztElapsed()} or nil
  return JSON.encode({cactuar_turn_totals = totals, cactuar_started = CZT.started == true,
                      cactuar_turn_numbers = turns, cactuar_turn = running})
end

-- Where the state lives. TTS rewinds restore objects' fields (memo, GM notes) but
-- NOT scripts' saved data: Global.script_state and the Timers' own turn counts came
-- back empty after a rewind (tested 2026-10-19), and a rewind doesn't call onSave.
-- So the state is written, on every turn change and every few seconds, to the memo
-- of a Cactuar tile (the build places both; c4c7a1 first). Global.script_state is
-- written too, for a table without tiles.
local CZT_STORE = {"c4c7a1", "c4c7a2"}

local function cztStoreObject()
  for _, guid in ipairs(CZT_STORE) do
    local o = nil
    pcall(function() o = getObjectFromGUID(guid) end)
    if o ~= nil then return o end
  end
  return nil
end

local function cztPersist()
  local state = cztState()
  pcall(function() Global.script_state = state end)
  local store = cztStoreObject()
  if store then pcall(function() store.memo = state end) end
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
      local c = Color.fromString(color)
      if index then                                       -- restyle one an older version made
        obj.editButton({index = index, position = CZT_LABEL.position, font_size = CZT_LABEL.font_size,
                        font_color = {c.r, c.g, c.b, CZT_LABEL.alpha}})
      elseif #buttons >= CZT_TIMER_BUTTONS then
        local n = #buttons                                -- ours becomes index n
        obj.createButton({
          click_function = "cztNoop", function_owner = Global, label = "",
          position = CZT_LABEL.position, width = 0, height = 0, font_size = CZT_LABEL.font_size,
          color = {0, 0, 0, 0}, font_color = {c.r, c.g, c.b, CZT_LABEL.alpha},
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

local function cztSeated(color)
  local seated = false
  pcall(function() seated = Player[color].seated end)
  return seated
end

-- Shown for every seated player (and anyone with time banked), all the time.
local function cztShow(color)
  local t = CZT.timers[color]
  if not t or t.obj == nil then return end
  local total = cztTotal(color)
  local shown = CZT.started and not CZT.hidden and (total > 0 or cztSeated(color))
  local label = shown and ("total " .. cztClock(total)) or ""
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

-- Bank the finished turn and start timing the next one, once the game has started.
function cztSwitch(color)
  if CZT.color then
    CZT.total[CZT.color] = cztTotal(CZT.color)
    local finished = CZT.color
    CZT.color, CZT.start = nil, nil
    cztShow(finished)
  end
  if CZT.started and color and cztSeat(color) then
    CZT.color, CZT.start, CZT.announced = color, os.time(), {}
  end
  cztShow(color)
  cztPersist()
end

-- Before the "Who goes first?" roll the game hasn't started: the table's own
-- turn clocks are kept quiet (their timerOn), and nothing is timed.
local function cztTableClocks(on)
  for _, t in pairs(CZT.timers) do
    pcall(function()
      t.obj.setVar("timerOn", on)
      if not on then t.obj.call("updateButtons", "     ") end
    end)
  end
end

-- True when the table's own clocks have counted turns: a game is in progress. A
-- fresh table's Timers all start at 0.
local function cztTurnsPlayed()
  for _, t in pairs(CZT.timers) do
    local n = 0
    pcall(function() n = tonumber(t.obj.getVar("turnN")) or 0 end)
    if n > 0 then return true end
  end
  return false
end

-- The table's own turn clock starts on a turn change, so a started game loaded
-- mid-turn shows it blank. Switch the clocks on, and start the current player's,
-- keeping its turn count: its onPlayerTurn would otherwise add one. A clock
-- already running just gets its turn number shown again.
local function cztStartTableClock()
  cztTableClocks(true)
  local t = CZT.color and CZT.timers[CZT.color]
  if not t or t.obj == nil then return end
  if t.obj.getVar("timerID") ~= nil then
    pcall(function()
      t.obj.editButton({index = 5, label = "turn"})
      t.obj.editButton({index = 6, width = 400, height = 400, label = t.obj.getVar("turnN")})
    end)
    return
  end
  local before = tonumber(t.obj.getVar("turnN")) or 0
  pcall(function()
    t.obj.call("onPlayerTurn", Player[CZT.color])
    if before > 0 then
      t.obj.setVar("turnN", before)
      t.obj.call("updateSave")
      t.obj.editButton({index = 6, label = before})
    end
  end)
end

-- The seat the die landed on: its faces carry seated players' Steam names, or
-- colours for empty seats, or "Roll again to see who".
local function cztDieColor(value)
  if type(value) ~= "string" then return nil end
  for _, c in ipairs(CZ.seats) do
    local name = nil
    pcall(function() name = Player[c].steam_name end)
    if value == c or (name and value == name) then return c end
  end
  return nil
end

-- Turn 1: zero every total and the table's turn counters, and give the turn to
-- the player the die picked. Their clock and total start now.
function cztStartGame(color)
  CZT.total, CZT.announced, CZT.color, CZT.start = {}, {}, nil, nil
  for _, t in pairs(CZT.timers) do
    pcall(function()
      t.obj.setVar("turnN", 0)
      t.obj.call("updateSave")
      t.obj.setVar("timerOn", true)
    end)
  end
  CZT.started = true
  if not Turns.enable then Turns.enable = true end
  if Turns.turn_color == color then
    -- Already their turn, so no turn event fires: start both clocks here.
    cztSwitch(color)
    local t = CZT.timers[color]
    if t then pcall(function() t.obj.call("onPlayerTurn", Player[color]) end) end
  else
    Turns.turn_color = color             -- fires onPlayerTurn: turn 1 on both clocks
  end
  cztShowAll()
  cztPersist()
  local who = color
  pcall(function() who = Player[color].steam_name or color end)
  broadcastToAll("New game! " .. who .. " goes first. Turn 1.", {0.6, 0.9, 0.6})
end

-- The first seated player's turn starts the game: every total and the table's
-- turn counters from zero, and this turn is turn 1. The Timer object's own
-- onPlayerTurn may run before or after ours, so its count is settled a frame later.
function cztFirstTurn(color)
  CZT.total, CZT.announced, CZT.started = {}, {}, true
  for _, t in pairs(CZT.timers) do
    pcall(function()
      t.obj.setVar("turnN", 0)
      t.obj.call("updateSave")
      t.obj.setVar("timerOn", true)
    end)
  end
  cztSwitch(color)
  Wait.frames(function()
    local t = CZT.timers[color]
    if not t then return end
    pcall(function()
      if t.obj.getVar("timerID") == nil then t.obj.call("onPlayerTurn", Player[color]) end
      t.obj.setVar("turnN", 1)
      t.obj.call("updateSave")
      t.obj.editButton({index = 5, label = "turn"})
      t.obj.editButton({index = 6, width = 400, height = 400, label = 1})
    end)
  end, 1)
  cztShowAll()
  cztPersist()
  local who = color
  pcall(function() who = Player[color].steam_name or color end)
  broadcastToAll(who .. " takes the first turn. Timers started.", {0.6, 0.9, 0.6})
end

-- "timers on" in a game that isn't started (a rewind, or a save loaded mid-game):
-- start timing from the current turn, keeping every turn number and total. No
-- die roll, which would restart the game at turn 1.
function cztResume()
  if CZT.started then return end
  CZT.started, CZT.announced = true, {}
  if Turns.enable and cztSeat(Turns.turn_color) then
    CZT.color, CZT.start = Turns.turn_color, os.time()
  end
  cztStartTableClock()
  cztShowAll()
  cztPersist()
  broadcastToAll("Timers resumed from the current turn.", {0.6, 0.9, 0.6})
end

-- The die was rolled: stop everything, then start once it settles.
function cztRolled(die)
  CZT.started, CZT.total, CZT.announced, CZT.color, CZT.start = false, {}, {}, nil, nil
  cztTableClocks(false)
  cztShowAll()
  cztPersist()
  local function settle()
    local value = nil
    pcall(function() value = die.getRotationValue() end)
    local color = cztDieColor(value)
    if color then
      cztStartGame(color)
    else
      broadcastToAll("Roll the die again to see who goes first.", {1, 0.8, 0.4})
    end
  end
  Wait.condition(settle, function()
    local resting = true
    pcall(function() resting = die.resting end)
    return resting
  end, 15, settle)
end

local function cztSaved()
  local saved = nil
  local store = cztStoreObject()
  if store then pcall(function() saved = JSON.decode(store.memo) end) end
  if type(saved) ~= "table" or saved.cactuar_started == nil then
    pcall(function() saved = JSON.decode(Global.script_state) end)
  end
  return type(saved) == "table" and saved or {}
end

-- Pick up a loaded or rewound game from the stored state: whether it started,
-- the totals, the turn numbers, and the running turn (continued, not restarted).
local function cztRestore()
  CZT.restored = true
  local saved = cztSaved()
  CZT.noSavedState = saved.cactuar_started == nil
  CZT.started = saved.cactuar_started == true
  CZT.total = CZT.started and type(saved.cactuar_turn_totals) == "table" and saved.cactuar_turn_totals or {}
  CZT.turnNumbers = CZT.started and type(saved.cactuar_turn_numbers) == "table" and saved.cactuar_turn_numbers or nil
  CZT.color, CZT.start = nil, nil
  if CZT.started and Turns and Turns.enable and cztSeat(Turns.turn_color) then
    CZT.color, CZT.start = Turns.turn_color, os.time()
    -- The same turn as when the state was stored: continue it rather than restart.
    -- Its elapsed time is in the stored total already, so move it out of the total.
    local r = saved.cactuar_turn
    local elapsed = type(r) == "table" and r.color == CZT.color and math.floor(tonumber(r.elapsed) or 0) or 0
    if elapsed > 0 then
      CZT.start = os.time() - elapsed
      CZT.total[CZT.color] = math.max(0, (CZT.total[CZT.color] or 0) - elapsed)
      for i, line in ipairs(CZT.lines) do
        if elapsed >= line.at then CZT.announced[i] = true end   -- don't repeat a line
      end
      CZT.resumed = {color = CZT.color, elapsed = elapsed}
    end
  end
end

function cztTick()
  if not CZT.attached then
    CZT.attached = cztAttach()
    if CZT.attached then
      if not CZT.restored then cztRestore() end
      if CZT.started then
        -- A rewind resets the table's own turn counters: put back the saved ones.
        for c, n in pairs(CZT.turnNumbers or {}) do
          local t = CZT.timers[c]
          if t and tonumber(n) and tonumber(n) > 0 then
            pcall(function()
              t.obj.setVar("turnN", tonumber(n))
              t.obj.call("updateSave")
            end)
          end
        end
        CZT.turnNumbers = nil
        cztStartTableClock()
        -- And the running turn's clock picks up where the snapshot left it.
        local r = CZT.resumed
        local t = r and CZT.timers[r.color]
        if t then pcall(function() t.obj.setVar("tdiff", r.elapsed) end) end
        CZT.resumed = nil
      elseif CZT.noSavedState and cztTurnsPlayed() then
        cztResume()            -- a game in progress whose snapshot lacked our state
      else
        cztTableClocks(false)
      end
      cztShowAll()
    end
  end
  CZT.ticks = (CZT.ticks or 0) + 1
  if CZT.ticks % 5 == 0 then cztShowAll() end     -- players sit down and stand up
  if CZT.ticks % 10 == 0 and CZT.started then cztPersist() end
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
CZT_BASE = CZT_BASE or {turn = onPlayerTurn, randomize = onObjectRandomize, chat = onChat, save = onSave}

-- Turn events TTS fires while the table is still loading don't start a game.
function onPlayerTurn(player, previous)
  local color = player and player.color
  if not CZT.started and CZT.restored and cztSeat(color) and os.time() - (CZT.loadedAt or 0) > 5 then
    cztFirstTurn(color)
  else
    cztSwitch(color)
  end
  if CZT_BASE.turn then return CZT_BASE.turn(player, previous) end
end

-- Only a seated player's roll starts a game. The die's own script rebuilds the
-- die (setCustomObject + reload) on load and whenever someone changes seats, and
-- TTS reports that as a randomize too: it must not start or restart the game.
function onObjectRandomize(obj, color)
  if obj and cztIsStartDie(obj) and cztSeat(color) and os.time() - (CZT.loadedAt or 0) > 10 then
    cztRolled(obj)
  end
  if CZT_BASE.randomize then return CZT_BASE.randomize(obj, color) end
end

function onChat(message, player)
  local m = string.lower(message or "")
  if m == "announcer off" then CZT.muted = true; broadcastToAll("Announcer muted.", {0.7, 0.7, 0.7})
  elseif m == "announcer on" then CZT.muted = false; broadcastToAll("Announcer on.", {0.7, 0.7, 0.7})
  elseif m == "announcer test" then cztAnnounce(CZT.lines[1], player and player.color or "White")
  elseif m == "timers off" then CZT.hidden = true; cztShowAll()
  elseif m == "timers on" then CZT.hidden = false; cztResume(); cztShowAll()
  end
  if CZT_BASE.chat then return CZT_BASE.chat(message, player) end
end

-- The totals live in Global's save (the base table saves nothing there), so a
-- reloaded game keeps them. The running turn is banked into its seat's total.
function onSave()
  if CZT_BASE.save then return CZT_BASE.save() end
  return cztState()
end

CZT.loadedAt = (cztPrevious and cztPrevious.loadedAt) or os.time()

-- Start ticking once loaded. A game nobody has rolled for waits for the die; a
-- started game (from its save) times the current turn from now; a live patch
-- carries everything over.
if cztPrevious then
  CZT.total, CZT.color, CZT.start = cztPrevious.total or {}, cztPrevious.color, cztPrevious.start
  CZT.announced, CZT.muted, CZT.hidden = cztPrevious.announced or {}, cztPrevious.muted, cztPrevious.hidden
  CZT.soundBase = cztPrevious.soundBase
  if cztPrevious.started == nil then CZT.started = cztPrevious.color ~= nil else CZT.started = cztPrevious.started end
  CZT.restored = true
else
  -- The saved state is read once the table's objects exist (cztRestore, at attach):
  -- when a game loads or rewinds, this script runs before the tile holding it does.
  CZT.restored = false
end
CZT.ticker = Wait.time(cztTick, 1, -1)
