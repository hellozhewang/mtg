-- One shared FF14 soundtrack. Pause/resume the loaded song between eligible
-- turns; switching songs restarts them (MusicPlayer exposes no seek API).
-- @MUSIC_COLORS@
local czmPrevious = CZM
if czmPrevious and czmPrevious.ticker then pcall(function() Wait.stop(czmPrevious.ticker) end) end
CZM = {
  theme = "sounds/ff14_theme.wav", ultima = "sounds/ff14_ultima.wav",
  titan = "sounds/ff14_titan.wav", thordan = "sounds/ff14_thordan.wav",
  hades = "sounds/ff14_hades.wav", locus = "sounds/ff14_alexander.wav",
  garuda = "sounds/ff14_garuda.wav", ifrit = "sounds/ff14_ifrit.wav",
  priority = {"titan", "ultima", "thordan", "hades", "locus", "garuda", "ifrit"},
  titles = {theme = "Prelude / Discoveries", titan = "Titan", ultima = "Ultima",
    thordan = "Thordan - Heroes", hades = "Hades - Who Brings Shadow",
    locus = "Alexander - Locus", garuda = "Garuda", ifrit = "Ifrit"},
  threshold = 10, counts = {}, status = "idle", serial = 0,
  cannonFired = false, disabled = false, ready = false,
  colorCache = {},
}

local function czmURL(track)
  return (CZT.soundBase or CZ.base) .. CZM[track]
end

-- Tags are explicit overrides for custom tokens / changed characteristics.
-- Names, mana symbols, rules mentions and object tint never imply card color.
local function czmTraits(meta)
  local tags, colors, colorTagged = {}, "", false
  local names = {white = "W", blue = "U", black = "B", red = "R", green = "G"}
  for _, tag in ipairs(meta.tags or meta.Tags or {}) do
    tag = tostring(tag):lower()
    tags[tag] = true
    if names[tag] then colors, colorTagged = colors .. names[tag], true end
    if tag == "colorless" then colorTagged = true end
  end
  if tags.colorless then colors = "" end
  local name = meta.nickname or meta.Nickname or meta.name or ""
  local typ = meta.type_line or meta.TypeLine or name:match("[\r\n]+([^\r\n]+)") or ""
  typ = typ:gsub("%b[]", ""):gsub("<[^>]*>", ""):lower()
  local function has(word) return tags[word] or typ:find("%f[%a]" .. word .. "%f[%A]") ~= nil end
  if not colorTagged then
    colors = meta.colors or meta.Colors
    if type(colors) == "table" then colors = table.concat(colors) end
    local stored = CZM_CARDS or {names = {}, images = {}}
    if colors == nil then
      local key = name:match("^[^\r\n]*"):gsub("%b[]", ""):gsub("<[^>]*>", "")
        :gsub("^%s+", ""):gsub("%s+$", ""):gsub("[A-Z]", string.lower)
      colors = stored.names[key]
      -- Exact printing wins, especially for same-named tokens of different colors.
      local sheets, id = meta.CustomDeck or {}, math.floor((tonumber(meta.CardID) or 0) / 100)
      local sheet = sheets[tostring(id)] or sheets[id]
      if sheet then colors = stored.images[(sheet.FaceURL or ""):gsub("%?.*$", "")] or colors end
    end
  end
  colors = type(colors) == "string" and colors:upper() or ""
  return {titan = has("goblin"), ultima = has("artifact"),
    thordan = has("creature") and colors:find("W", 1, true) ~= nil,
    hades = has("creature") and colors:find("B", 1, true) ~= nil,
    locus = has("creature") and colors:find("U", 1, true) ~= nil,
    garuda = has("creature") and colors:find("G", 1, true) ~= nil,
    ifrit = has("creature") and colors:find("R", 1, true) ~= nil}
end

local function czmObjects(zone)
  if not zone then return {} end
  local ok, objects = pcall(function() return zone.getObjects(true) end)
  return ok and objects or {}
end

function czmCountBattlefield()
  local counts, excluded, seen = {}, {}, {}
  -- The battlefield zones already end before the commander/library/exile/GY
  -- columns. Explicitly exclude library/GY objects as well if zones overlap.
  for _, color in ipairs(CZ.seats) do
    local seat = data and data[color]
    if seat then
      for _, key in ipairs({"libraryZone", "graveyard", "exile"}) do
        for _, obj in ipairs(czmObjects(seat[key])) do excluded[obj] = true end
      end
    end
  end
  for _, color in ipairs(CZ.seats) do
    local count, seat = {}, data and data[color]
    for _, track in ipairs(CZM.priority) do count[track] = 0 end
    local function add(meta)
      for track, matches in pairs(czmTraits(meta)) do
        if matches then count[track] = count[track] + 1 end
      end
    end
    for _, obj in ipairs(czmObjects(seat and seat.playmat)) do
      if not excluded[obj] and not seen[obj] then
        seen[obj] = true
        pcall(function()
          if obj.is_face_down then return end
          if obj.type == "Deck" or obj.tag == "Deck" then
            -- Container metadata omits CustomDeck; fetch full data once per
            -- scan to resolve differently colored tokens by their exact art.
            local cards = obj.getObjects()
            if obj.getData then
              local ok, full = pcall(obj.getData)
              if ok and full and full.ContainedObjects then
                cards = full.ContainedObjects
                for _, card in ipairs(cards) do card.CustomDeck = card.CustomDeck or full.CustomDeck end
              end
            end
            for _, card in ipairs(cards) do add(card) end
            return
          end
          local name = obj.getName()
          local cached = CZM.colorCache[obj]
          if not cached or cached.name ~= name then
            local ok, meta = pcall(function() return obj.getData() end)
            cached = {name = name, meta = ok and meta or {}}
            CZM.colorCache[obj] = cached
          end
          local meta = cached.meta
          meta.nickname, meta.tags = name, obj.getTags()
          add(meta)
          for _, attachment in ipairs(obj.getAttachments() or {}) do
            add(attachment)
          end
        end)
      end
    end
    counts[color] = count
  end
  return counts
end

-- Keep existing artifact diagnostics compatible; detailed counts live in .battlefields.
function czmCountArtifacts()
  local counts = {}
  for color, totals in pairs(czmCountBattlefield()) do counts[color] = totals.ultima end
  return counts
end

function czmSavedState()
  return {cannonFired = CZM.cannonFired == true, disabled = CZM.disabled == true}
end

function czmBlocksVoice()
  -- Keep the loaded battle song even while paused so voices cannot lose its position.
  return CZM.track ~= nil and (CZM.track ~= "theme" or not CZM.cannonFired)
end

local function czmRestore()
  if not CZT.restored or not data then return false end
  for _, color in ipairs(CZ.seats) do
    if not data[color] or not data[color].playmat then return false end
  end
  local saved = nil
  for _, guid in ipairs({"c4c7a1", "c4c7a2"}) do
    local obj = getObjectFromGUID(guid)
    if obj then pcall(function() saved = JSON.decode(obj.memo) end) end
    if type(saved) == "table" and saved.cactuar_started ~= nil then break end
  end
  if type(saved) ~= "table" then pcall(function() saved = JSON.decode(Global.script_state) end) end
  local music = type(saved) == "table" and saved.cactuar_music or nil
  CZM.cannonFired = CZM.cannonFired or CZT.started == true
    or type(music) == "table" and music.cannonFired == true
  if not CZM.settingChanged then CZM.disabled = type(music) == "table" and music.disabled == true end
  CZM.ready = true
  return true
end

local function czmPause()
  if CZM.track and CZM.status ~= "loading" and CZM.status ~= "paused" and CZM.status ~= "error" then
    local ok, err = pcall(MusicPlayer.pause)
    CZM.status = ok and "paused" or "error"
    if not ok then CZM.error = tostring(err); print("Cactuar music: " .. CZM.error) end
  end
end

local function czmLoad(track)
  local state = CZM
  -- Cancel a previously queued announcer callback before taking the channel.
  CZT.audioSerial = (CZT.audioSerial or 0) + 1
  state.serial, state.track, state.status = state.serial + 1, track, "loading"
  state.error, state.url = nil, czmURL(track)
  local serial = state.serial
  local ok, err = pcall(function()
    local clip = {url = state.url, title = "FFXIV - " .. state.titles[track]}
    -- Replace the inherited placeholder playlist too, so repeat/next cannot
    -- return to an unrelated base-table sound. Enable looping only when ready.
    MusicPlayer.repeat_track = false
    MusicPlayer.pause()
    MusicPlayer.setPlaylist({clip})
    MusicPlayer.setCurrentAudioclip(clip)
    MusicPlayer.playlist_index = 0
    Wait.condition(function()
      if CZM ~= state or state.serial ~= serial then return end
      state.status = "ready"
      czmTick() -- recheck the current turn/count; never play a stale trigger
    end, function()
      local loaded, clip = pcall(MusicPlayer.getCurrentAudioclip)
      return MusicPlayer.loaded and loaded and clip and clip.url == state.url
    end, 90, function()
      if CZM == state and state.serial == serial then
        state.status, state.error = "error", "Soundtrack load timed out"
        print("Cactuar music: " .. state.error)
      end
    end)
  end)
  if not ok then state.status, state.error = "error", tostring(err); print("Cactuar music: " .. state.error) end
end

function czmTick()
  if not CZM.ready and not czmRestore() then return end
  CZM.battlefields, CZM.counts = czmCountBattlefield(), {}
  for color, totals in pairs(CZM.battlefields) do CZM.counts[color] = totals.ultima end
  if CZM.disabled then czmPause(); return end
  local active = Turns.enable and Turns.turn_color or nil
  local wanted = not CZM.cannonFired and "theme" or nil
  if CZM.cannonFired and active then
    for _, track in ipairs(CZM.priority) do
      if (CZM.battlefields[active] or {})[track] and CZM.battlefields[active][track] >= CZM.threshold then
        wanted = track; break
      end
    end
  end
  if wanted and wanted ~= CZM.track then czmLoad(wanted); return end
  if not wanted then czmPause(); return end
  if CZM.status ~= "loading" and CZM.status ~= "playing" and CZM.status ~= "error" then
    MusicPlayer.repeat_track = true
    local ok, result = pcall(MusicPlayer.play)
    CZM.status = ok and result ~= false and "playing" or "error"
    if not ok then CZM.error = tostring(result); print("Cactuar music: " .. CZM.error) end
  end
end

function czmCannonFired()
  CZM.cannonFired = true
  -- Stop immediately, even if the prelude download is still pending.
  if CZM.track == "theme" then
    CZM.serial = CZM.serial + 1
    MusicPlayer.repeat_track = false
    MusicPlayer.pause()
    MusicPlayer.setPlaylist({}) -- no prelude fallback after a one-shot voice clip
    CZM.status = "paused"
  end
  if cztPersist then cztPersist() end
  czmTick()
end

local function czmQueue()
  if CZM.queued then return end
  local state = CZM
  state.queued = true
  Wait.frames(function()
    if CZM ~= state then return end
    state.queued = nil
    czmTick()
  end, 2)
end

CZMB = CZMB or {turn = onPlayerTurn, enter = onObjectEnterScriptingZone,
  leave = onObjectLeaveScriptingZone, destroy = onObjectDestroy,
  state = onObjectStateChange, chat = onChat}
function onPlayerTurn(player, previous)
  czmTick() -- claim/pause soundtrack before the turn announcer can replace it
  if CZMB.turn then return CZMB.turn(player, previous) end
end
function onObjectEnterScriptingZone(zone, obj)
  czmQueue()
  if CZMB.enter then return CZMB.enter(zone, obj) end
end
function onObjectLeaveScriptingZone(zone, obj)
  czmQueue()
  if CZMB.leave then return CZMB.leave(zone, obj) end
end
function onObjectDestroy(obj)
  CZM.colorCache[obj] = nil
  czmQueue()
  if CZMB.destroy then return CZMB.destroy(obj) end
end
function onObjectStateChange(obj, old)
  CZM.colorCache[obj] = nil
  czmQueue()
  if CZMB.state then return CZMB.state(obj, old) end
end
function onChat(message, player)
  local m = message:lower():gsub("^%s+", ""):gsub("%s+$", "")
  if m == "music off" or m == "music on" then
    CZM.disabled = m == "music off"
    CZM.settingChanged = true
    if CZM.status == "error" and not CZM.disabled then CZM.track, CZM.status = nil, "idle" end
    czmTick()
    if cztPersist then cztPersist() end
  end
  if CZMB.chat then return CZMB.chat(message, player) end
end

if czmPrevious then
  for _, key in ipairs({"ready", "cannonFired", "disabled", "settingChanged", "track", "url", "status", "counts"}) do
    CZM[key] = czmPrevious[key]
  end
  if CZM.status == "loading" then CZM.track, CZM.status = nil, "idle" end
  if CZM.track and CZM.url ~= czmURL(CZM.track) then CZM.track, CZM.status = nil, "idle" end
end
CZM.ticker = Wait.time(czmTick, 0.5, -1)
