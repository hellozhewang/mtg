-- Battlefield-only counting and one pause/resume soundtrack, with real turn hooks.
local checks = 0
local function check(value, message) checks = checks + 1; assert(value, message) end
local function serialize(v)
  if type(v) ~= "table" then return type(v) == "string" and string.format("%q", v) or tostring(v) end
  local out = {}
  for k, x in pairs(v) do out[#out + 1] = "[" .. string.format("%q", k) .. "]=" .. serialize(x) end
  return "{" .. table.concat(out, ",") .. "}"
end
JSON = {encode = serialize, decode = function(v) return assert(load("return " .. v))() end}
CZ = {base = "https://example.test/tts/", seats = {"White", "Red", "Yellow", "Green", "Blue", "Purple"}}
Global, Player = {}, {}
local tile, now = {}, 1000
os.time = function() return now end
function getObjectFromGUID(guid) if guid == "c4c7a1" then return tile end end
function getAllObjects() return {} end
function broadcastToAll() end
Turns = {enable = true, turn_color = "White"}
local frames, waits, timers, nextWait = {}, {}, {}, 0
Wait = {
  frames = function(fn) frames[#frames + 1] = fn end,
  condition = function(fn, cond, _, timeout)
    if cond() then fn() else waits[#waits + 1] = {fn = fn, cond = cond, timeout = timeout} end
  end,
  time = function(fn) nextWait = nextWait + 1; timers[nextWait] = fn; return nextWait end,
  stop = function(id) timers[id] = nil end,
}
local function flush()
  local pending = frames; frames = {}
  for _, fn in ipairs(pending) do fn() end
end
local loads, plays, pauses, position = 0, 0, 0, 0
local current, playing = {url = "base://playlist"}, false
local playlist = {{url = "base://playlist", title = "----"}}
MusicPlayer = {loaded = true,
  getCurrentAudioclip = function() return current end,
  setPlaylist = function(value) playlist = value end,
  setCurrentAudioclip = function(clip) loads = loads + 1; current = clip; position = 0; playing = false end,
  play = function() plays = plays + 1; playing = true; return true end,
  pause = function() pauses = pauses + 1; playing = false; return true end,
}
local function advance(seconds) now = now + seconds; if playing then position = position + seconds end end
local function zone() local z = {objects = {}}; z.getObjects = function() return z.objects end; return z end
local function card(typ, name)
  local c = {type = "Card", tags = {}, attachments = {}, nickname = (name or "Card") .. "\n" .. typ .. " 2CMC"}
  c.getName = function() return c.nickname end
  c.getTags = function() return c.tags end
  c.getAttachments = function() return c.attachments end
  return c
end
data = {}
for _, color in ipairs(CZ.seats) do
  data[color] = {playmat = zone(), libraryZone = zone(), graveyard = zone(), exile = zone()}
  Player[color] = {color = color, seated = true, steam_name = color}
end
local function populate(color, count)
  local list = {}
  for i = 1, count do list[i] = card(i % 2 == 0 and "Artifact Creature — Golem" or "Artifact — Treasure") end
  data[color].playmat.objects = list
end
local baseTurns, baseEnters, baseChats = 0, 0, 0
function onPlayerTurn() baseTurns = baseTurns + 1 end
function onObjectEnterScriptingZone() baseEnters = baseEnters + 1 end
function onChat() baseChats = baseChats + 1 end
dofile("tts/cactuar_turns.lua")
CZT.restored, CZT.started, CZT.loadedAt = true, false, 0
dofile("tts/cactuar_music.lua")

czmTick()
check(current.url:find("ff14_theme.wav", 1, true) and playing and MusicPlayer.repeat_track, "fresh table loops the original FF14 WAV")
check(#playlist == 1 and playlist[1].url == current.url and MusicPlayer.playlist_index == 0, "looping uses only the current theme, never an inherited placeholder track")
local firstLoads = loads
czmTick(); czmTick()
check(loads == firstLoads, "repeated scans do not reload or duplicate the prelude")
local beforeFirePauses = pauses
czmCannonFired()
check(not playing and CZM.cannonFired and pauses == beforeFirePauses + 1, "cannon firing stops the prelude immediately")
check(#playlist == 0 and not MusicPlayer.repeat_track, "cannon firing clears the prelude playlist so voice completion cannot resume it")
check(JSON.decode(tile.memo).cactuar_music.cannonFired, "cannon state persists even before a winner is chosen")
CZT.started = true

populate("White", 9); czmTick()
check(CZM.counts.White == 9 and not playing, "nine artifacts do not trigger Ultima")
local other = card("Creature — Human", "Artifact Collector")
other.description = "Artifacts you control get a bonus."
table.insert(data.White.playmat.objects, other)
local facedown = card("Artifact"); facedown.is_face_down = true
table.insert(data.White.playmat.objects, facedown)
local library, graveyard, exile = card("Artifact"), card("Artifact"), card("Artifact")
for _, entry in ipairs({{library, "libraryZone"}, {graveyard, "graveyard"}, {exile, "exile"}}) do
  table.insert(data.White.playmat.objects, entry[1]); data.White[entry[2]].objects = {entry[1]}
end
czmTick()
check(CZM.counts.White == 9, "rules mentions, face-down cards and excluded zones never count")
table.insert(data.White.playmat.objects, card("Artifact Land")); czmTick()
check(CZM.counts.White == 10 and current.url:find("ff14_ultima.wav", 1, true) and playing, "ten battlefield artifacts start one looping original Ultima WAV")
check(#playlist == 1 and playlist[1].url == current.url, "Ultima replaces every previous playlist entry")
local ultimaLoads = loads
advance(23); czmTick()
check(position == 23 and loads == ultimaLoads, "steady qualification does not restart the music")
Turns.turn_color = "Red"; onPlayerTurn(Player.Red, Player.White)
check(not playing and position == 23 and loads == ultimaLoads, "nonqualifying player's turn pauses at the same playhead")
check(CZT.audioStatus == "suppressed for soundtrack" and baseTurns == 1, "real turn voice is suppressed and the base handler still runs")
advance(30)
Turns.turn_color = "White"; onPlayerTurn(Player.White, Player.Red)
check(playing and position == 23 and loads == ultimaLoads, "eligible player's next turn resumes without replacing the clip")
advance(5); populate("Red", 12)
Turns.turn_color = "Red"; onPlayerTurn(Player.Red, Player.White)
check(playing and position == 28 and loads == ultimaLoads, "another eligible player shares the one continuous Ultima instance")
populate("Red", 9); onObjectLeaveScriptingZone(data.Red.playmat, nil); flush()
check(not playing and CZM.counts.Red == 9, "dropping below ten on the active player's battlefield pauses promptly")
check(CZM.counts.White == 10, "another player's threshold does not play music on the wrong turn")
populate("Red", 10); onObjectEnterScriptingZone(data.Red.playmat, nil); flush()
check(playing and position == 28 and loads == ultimaLoads and baseEnters == 1, "entering the zone resumes once and preserves the base zone event")
onChat("announcer test", Player.Red)
check(loads == ultimaLoads, "slow-turn test voices cannot overwrite the retained Ultima")
onChat("music off", Player.Red)
check(not playing, "music off pauses without losing its position")
onChat("music on", Player.Red)
check(playing and position == 28 and loads == ultimaLoads and baseChats >= 3, "music on resumes and preserves existing chat handlers")

-- Stacks count each artifact, not deck quantity or a misleading deck name.
local stack = {type = "Deck", getObjects = function() return {
  {name = "Sol Ring\nArtifact 1CMC"}, {nickname = "Golem\nArtifact Creature — Golem"},
  {name = "Collector\nCreature — Human", description = "Make artifacts."}} end}
data.Yellow.playmat.objects = {stack, card("Creature")}
local tagged = card("Creature"); tagged.tags = {"Artifact"}
local attached = card("Creature"); attached.attachments = {{Nickname = "Equipment\nArtifact — Equipment"}}
data.Green.playmat.objects = {tagged, attached}
czmTick()
check(CZM.counts.Yellow == 2 and CZM.counts.Green == 2, "artifact stacks, tags and attached equipment count without inspecting rules text")
Turns.enable = false; czmTick()
check(not playing, "disabling turns pauses Ultima")
Turns.enable = true; czmTick()
check(playing and loads == ultimaLoads, "reenabling a qualifying turn resumes the same clip")

-- A live script patch must not restart a playing track or leave a second ticker.
local oldTicker = CZM.ticker
dofile("tts/cactuar_music.lua"); czmTick()
check(timers[oldTicker] == nil and loads == ultimaLoads and playing, "live reload keeps the playhead and replaces its old ticker")

-- Saved midgame state never replays the prelude after a full module reload.
cztPersist(); CZM = nil
dofile("tts/cactuar_music.lua"); czmTick()
check(CZM.cannonFired and not current.url:find("ff14_theme", 1, true), "midgame restoration does not restart lobby music")

-- A cannon fired while a slow prelude download is pending cancels its callback.
CZM = nil; CZT.started = false; tile.memo, Global.script_state = nil, nil
MusicPlayer.loaded = false
dofile("tts/cactuar_music.lua"); czmTick()
check(CZM.status == "loading", "soundtrack loading is asynchronous")
populate("Red", 0); czmCannonFired()
local before = plays
for _, wait in ipairs(waits) do wait.fn() end
check(plays == before and not playing, "an obsolete prelude completion cannot play after the cannon fires")

-- Eligibility may disappear while Ultima downloads. Keep the file paused and
-- resume it later; neither the old trigger nor subsequent scans may restart it.
populate("Red", 10); czmTick()
local ultimaWait = waits[#waits]
populate("Red", 9); MusicPlayer.loaded = true; ultimaWait.fn()
check(not playing and CZM.status == "paused", "late Ultima loading rechecks a no-longer-eligible battlefield before playback")
local downloaded = loads
populate("Red", 10); czmTick()
check(playing and loads == downloaded, "a later eligible turn uses the already loaded Ultima")
data.Red.playmat.objects[1].nickname = "Changed face\nCreature — Human"
onObjectStateChange(data.Red.playmat.objects[1], "old"); flush()
check(CZM.counts.Red == 9 and not playing, "state/type changes on the active battlefield pause Ultima")

-- A chat mute issued during initial table setup must survive restoration.
CZM = nil; tile.memo, Global.script_state = nil, nil; CZT.restored = false
dofile("tts/cactuar_music.lua")
onChat("music off", Player.Red)
CZT.restored = true; czmTick()
check(CZM.disabled and not playing, "an early music off is not overwritten by the saved-state restore")

-- Seven battlefield triggers: threshold, exact priority, colors and turn gating.
CZM.disabled, CZM.cannonFired, CZM.ready = false, true, true
CZM_CARDS = {names = {soldier = "W", zombie = "B", merfolk = "U", elf = "G", dragon = "R",
  multicolor = "WUBRG", devoid = ""}, images = {["test://black-soldier"] = "B"}}
for _, color in ipairs(CZ.seats) do
  data[color].playmat.objects = {}; data[color].libraryZone.objects = {}
  data[color].graveyard.objects = {}; data[color].exile.objects = {}
end
Turns.enable, Turns.turn_color = true, "White"
local tracks = {"titan", "ultima", "thordan", "hades", "locus", "garuda", "ifrit"}
local types = {"Creature — Goblin", "Artifact", "Creature — Soldier", "Creature — Zombie",
  "Creature — Merfolk", "Creature — Elf", "Creature — Dragon"}
local names = {"Goblin", "Sol Ring", "Soldier", "Zombie", "Merfolk", "Elf", "Dragon"}
for i, track in ipairs(tracks) do
  data.White.playmat.objects = {}
  for j = 1, 9 do table.insert(data.White.playmat.objects, card(types[i], names[i])) end
  czmTick()
  check(not playing, "nine objects never trigger " .. track)
  table.insert(data.White.playmat.objects, card(types[i], names[i])); czmTick()
  check(playing and CZM.track == track and MusicPlayer.repeat_track, "ten battlefield objects loop " .. track)
  local selectedLoads = loads
  advance(3); czmTick()
  check(position == 3 and loads == selectedLoads, track .. " remains one instance without restarting")
  Turns.turn_color = "Red"; onPlayerTurn(Player.Red, Player.White)
  check(not playing and position == 3 and czmBlocksVoice(), track .. " pauses outside the qualifying player's turn and blocks voices")
  Turns.turn_color = "White"; onPlayerTurn(Player.White, Player.Red)
  check(playing and position == 3 and loads == selectedLoads, track .. " resumes unchanged on the qualifying turn")
  data.White.playmat.objects = {}; czmTick()
end

-- All thresholds satisfied together, then peel them off in the owner's priority.
for i = 1, #tracks do
  for j = 1, 10 do table.insert(data.White.playmat.objects, card(types[i], names[i])) end
end
for i, track in ipairs(tracks) do
  czmTick()
  check(playing and CZM.track == track, "priority chooses " .. track .. " before all remaining triggers")
  for j = 1, 10 do table.remove(data.White.playmat.objects, 1) end
end
czmTick(); check(not playing, "losing all seven thresholds pauses playback")

data.White.playmat.objects = {}
for i = 1, 10 do data.White.playmat.objects[i] = card("Artifact Creature — Goblin", "Multicolor") end
czmTick()
for _, track in ipairs(tracks) do check(CZM.battlefields.White[track] == 10, "one multicolor artifact Goblin counts once for " .. track) end
check(CZM.track == "titan", "Goblin priority beats artifact and all five colors on the same ten creatures")
data.White.playmat.objects = {card("Creature — Eldrazi", "Devoid"), card("Enchantment", "Soldier")}
czmTick()
check(CZM.battlefields.White.thordan == 0 and CZM.battlefields.White.ifrit == 0, "colorless devoid and colored noncreatures do not trigger creature colors")
local custom = card("Creature — Goblin"); custom.tags = {"White", "Blue", "Artifact"}
data.White.playmat.objects = {custom}; czmTick()
check(CZM.battlefields.White.thordan == 1 and CZM.battlefields.White.locus == 1 and CZM.battlefields.White.ultima == 1,
  "explicit tags support custom multicolor creatures and changed artifact types")
custom.tags = {"Colorless"}; czmTick()
check(CZM.battlefields.White.thordan == 0 and CZM.battlefields.White.locus == 0, "tag changes update without stale color caching")
local token = card("Token Creature — Soldier", "Soldier")
token.getData = function() return {CardID = 100, CustomDeck = {["1"] = {FaceURL = "test://black-soldier"}}} end
data.White.playmat.objects = {token}; czmTick()
check(CZM.battlefields.White.hades == 1 and CZM.battlefields.White.thordan == 0, "exact token image overrides an ambiguous shared name")
token.is_face_down = true; czmTick()
check(CZM.battlefields.White.hades == 0, "face-down colored creatures do not count")
token.is_face_down = false
data.White.exile.objects = {token}; czmTick()
check(CZM.battlefields.White.hades == 0, "exile excludes colored creatures even when zones overlap")
data.White.exile.objects = {}
data.White.playmat.objects = {{type = "Deck", getObjects = function() return {} end,
  getData = function() return {CustomDeck = {["1"] = {FaceURL = "test://black-soldier"}},
    ContainedObjects = {{Nickname = "Soldier\nToken Creature — Soldier", CardID = 100}}} end}}
czmTick()
check(CZM.battlefields.White.hades == 1 and CZM.battlefields.White.thordan == 0, "face-up stacks resolve token colors from the parent sheet")

-- A higher-priority trigger can replace a loading track. Old callbacks never play.
data.White.playmat.objects = {}; MusicPlayer.loaded = false
for i = 1, 10 do data.White.playmat.objects[i] = card("Creature — Dragon", "Dragon") end
czmTick(); local ifritWait = waits[#waits]
for i = 1, 10 do table.insert(data.White.playmat.objects, card("Creature — Goblin", "Goblin")) end
czmTick(); local titanWait = waits[#waits]
local beforeStale = plays
ifritWait.fn()
check(CZM.track == "titan" and CZM.status == "loading" and plays == beforeStale, "superseded load cannot play a lower-priority track")
MusicPlayer.loaded = true; titanWait.fn()
check(playing and CZM.track == "titan", "current highest-priority load starts once ready")

print(checks .. " music checks, 0 failed")
