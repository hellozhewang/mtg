-- Battle songs called by named cards on the active player's battlefield, and one
-- pause/resume soundtrack, with real turn hooks.
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
  Player[color] = {color = color, seated = true, steam_name = color, hands = {{}, {}}}
  local player = Player[color]
  -- On the real table indexing hands can throw past pcall: fail loudly if the
  -- music code ever goes back to that.
  player.getHandCount = function() error("music must not index player hands") end
  player.getHandObjects = function() error("music must not index player hands") end
end
-- Hand zones as TTS's Hands.getHands() returns them: each zone lists its objects.
Hands = {getHands = function()
  local zones = {}
  for _, color in ipairs(CZ.seats) do
    for i = 1, 2 do
      local hand = Player[color].hands[i]
      zones[#zones + 1] = {getObjects = function() return hand end}
    end
  end
  return zones
end}
-- A battlefield: filler permanents, plus Ultima when `ultima` is true.
local function populate(color, ultima)
  local list = {card("Artifact — Treasure", "Treasure"), card("Creature — Golem", "Golem")}
  if ultima then list[#list + 1] = card("Legendary Creature — God", "Ultima, Origin of Oblivion") end
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

-- Only the named card calls the song: lots of artifacts, rules mentions, face-down
-- copies and copies in the library, graveyard or exile do not.
data.White.playmat.objects = {}
for i = 1, 12 do data.White.playmat.objects[i] = card("Artifact — Treasure", "Treasure") end
czmTick()
check(CZM.battlefields.White.ultima == 0 and not playing, "twelve artifacts no longer call Ultima")
local mention = card("Creature — Human", "Ultima Fan"); mention.description = "Ultima, Origin of Oblivion is great."
local facedown = card("Legendary Creature — God", "Ultima, Origin of Oblivion"); facedown.is_face_down = true
table.insert(data.White.playmat.objects, mention); table.insert(data.White.playmat.objects, facedown)
local library, graveyard, exile = card("Legendary Creature — God", "Ultima, Origin of Oblivion"),
  card("Legendary Creature — God", "Ultima, Origin of Oblivion"), card("Legendary Creature — God", "Ultima, Origin of Oblivion")
for _, entry in ipairs({{library, "libraryZone"}, {graveyard, "graveyard"}, {exile, "exile"}}) do
  table.insert(data.White.playmat.objects, entry[1]); data.White[entry[2]].objects = {entry[1]}
end
czmTick()
check(CZM.battlefields.White.ultima == 0 and not playing, "mentions, face-down cards and excluded zones never call a song")
table.insert(data.White.playmat.objects, card("Legendary Creature — God", "Ultima, Origin of Oblivion")); czmTick()
check(CZM.battlefields.White.ultima == 1 and current.url:find("ff14_ultima.wav", 1, true) and playing, "Ultima, Origin of Oblivion on the battlefield loops Ultima")
check(#playlist == 1 and playlist[1].url == current.url, "Ultima replaces every previous playlist entry")
local ultimaLoads = loads
advance(23); czmTick()
check(position == 23 and loads == ultimaLoads, "steady qualification does not restart the music")
Turns.turn_color = "Red"; onPlayerTurn(Player.Red, Player.White)
check(not playing and position == 23 and loads == ultimaLoads, "another player's turn pauses at the same playhead")
check(CZT.audioStatus == "suppressed for soundtrack" and baseTurns == 1, "real turn voice is suppressed and the base handler still runs")
advance(30)
Turns.turn_color = "White"; onPlayerTurn(Player.White, Player.Red)
check(playing and position == 23 and loads == ultimaLoads, "the card owner's next turn resumes without replacing the clip")
advance(5); populate("Red", true)
Turns.turn_color = "Red"; onPlayerTurn(Player.Red, Player.White)
check(playing and position == 28 and loads == ultimaLoads, "another player with Ultima shares the one continuous instance")
populate("Red", false); onObjectLeaveScriptingZone(data.Red.playmat, nil); flush()
check(not playing and CZM.battlefields.Red.ultima == 0, "Ultima leaving the active player's battlefield pauses promptly")
check(CZM.battlefields.White.ultima == 1, "another player's Ultima does not play on the wrong turn")
populate("Red", true); onObjectEnterScriptingZone(data.Red.playmat, nil); flush()
check(playing and position == 28 and loads == ultimaLoads and baseEnters == 1, "entering the zone resumes once and preserves the base zone event")
onChat("announcer test", Player.Red)
check(loads == ultimaLoads, "slow-turn test voices cannot overwrite the retained Ultima")
onChat("music off", Player.Red)
check(not playing, "music off pauses without losing its position")
onChat("music on", Player.Red)
check(playing and position == 28 and loads == ultimaLoads and baseChats >= 3, "music on resumes and preserves existing chat handlers")
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
populate("Red", false); czmCannonFired()
local before = plays
for _, wait in ipairs(waits) do wait.fn() end
check(plays == before and not playing, "an obsolete prelude completion cannot play after the cannon fires")

-- The card may leave while Ultima downloads. Keep the file paused and resume it
-- later; neither the old trigger nor subsequent scans may restart it.
populate("Red", true); czmTick()
local ultimaWait = waits[#waits]
populate("Red", false); MusicPlayer.loaded = true; ultimaWait.fn()
check(not playing and CZM.status == "paused", "late Ultima loading rechecks a battlefield that lost its card before playback")
local downloaded = loads
populate("Red", true); czmTick()
check(playing and loads == downloaded, "a later eligible turn uses the already loaded Ultima")
local ultimaCard = data.Red.playmat.objects[#data.Red.playmat.objects]
ultimaCard.nickname = "Changed face\nCreature — Human"
onObjectStateChange(ultimaCard, "old"); flush()
check(CZM.battlefields.Red.ultima == 0 and not playing, "flipping the card to another face pauses the song")

-- A chat mute issued during initial table setup must survive restoration.
CZM = nil; tile.memo, Global.script_state = nil, nil; CZT.restored = false
dofile("tts/cactuar_music.lua")
onChat("music off", Player.Red)
CZT.restored = true; czmTick()
check(CZM.disabled and not playing, "an early music off is not overwritten by the saved-state restore")

-- A caller in hand is not on the battlefield, even though the hand sits inside the
-- playmat zone; neither is one being dragged on someone's cursor.
CZM.disabled, CZM.cannonFired, CZM.ready = false, true, true
for _, color in ipairs(CZ.seats) do
  data[color].playmat.objects = {}; data[color].libraryZone.objects = {}
  data[color].graveyard.objects = {}; data[color].exile.objects = {}
end
Turns.enable, Turns.turn_color = true, "White"
local inHand = card("Enchantment Creature — Saga Knight", "Summon: Knights of Round")
data.White.playmat.objects = {inHand}; Player.White.hands[1] = {inHand}; czmTick()
check(not playing and CZM.battlefields.White.thordan == 0, "a caller in hand does not play its song")
Player.White.hands[1] = {}; Player.White.hands[2] = {inHand}; czmTick()
check(not playing, "the second hand zone counts as hand too")
Player.White.hands[2] = {}; inHand.held_by_color = "White"; czmTick()
check(not playing, "a caller being dragged does not play its song")
inHand.held_by_color = nil; czmTick()
check(playing and CZM.track == "thordan", "the same card played onto the battlefield does")
data.White.playmat.objects = {}; czmTick()

-- Every song and every card that calls it, with turn gating.
CZM.disabled, CZM.cannonFired, CZM.ready = false, true, true
for _, color in ipairs(CZ.seats) do
  data[color].playmat.objects = {}; data[color].libraryZone.objects = {}
  data[color].graveyard.objects = {}; data[color].exile.objects = {}
end
Turns.enable, Turns.turn_color = true, "White"
local callers = {
  {"titan", "Summon: Titan", "Enchantment Creature — Saga Giant"},
  {"ultima", "Ultima, Origin of Oblivion", "Legendary Creature — God"},
  {"ultima", "Ultima Weapon", "Artifact Creature — Construct"},
  {"omega", "Omega, Heartless Evolution", "Legendary Artifact Creature — Robot"},
  {"thordan", "Summon: Knights of Round", "Enchantment Creature — Saga Knight"},
  {"hades", "Hades, Sorcerer of Eld", "Legendary Creature — Avatar"},
  {"locus", "Summon: Alexander", "Enchantment Artifact Creature — Saga Construct"},
  {"garuda", "Summon: Primal Garuda", "Enchantment Creature — Saga Elemental"},
  {"ifrit", "Clive, Ifrit's Dominant", "Legendary Creature — Human Noble Warrior"},
  {"ifrit", "Ifrit, Warden of Inferno", "Legendary Creature — Demon"},
  {"hades", "Y'shtola Rhul", "Legendary Creature — Cat Druid"},
  {"hades", "Y'shtola, Night's Blessed", "Legendary Creature — Cat Warlock"},
  {"hades", "G'raha Tia", "Legendary Creature — Cat Archer"},
  {"hades", "G'raha Tia, Scion Reborn", "Legendary Creature — Cat Wizard"},
  {"shiva", "Summon: Shiva", "Enchantment Creature — Saga Elemental"},
  {"shiva", "Shiva, Warden of Ice", "Legendary Enchantment Creature — Saga Elemental"},
  {"leviathan", "Summon: Leviathan", "Enchantment Creature — Saga Leviathan"},
  {"ramuh", "Summon: Esper Ramuh", "Enchantment Creature — Saga Wizard"},
  {"bahamut", "Summon: Bahamut", "Enchantment Creature — Saga Dragon"},
  {"gilgamesh", "Gilgamesh, Master-at-Arms", "Legendary Creature — Human Samurai"},
  {"dragonsong", "Estinien Varlineau", "Legendary Creature — Elf Warrior"},
  {"dragonsong", "Eye of Nidhogg", "Legendary Enchantment — Aura"},
  {"footfalls", "Venat, Heart of Hydaelyn", "Legendary Creature — Elder Wizard"},
  {"footfalls", "Hydaelyn, the Mothercrystal", "Legendary Creature — God"},
  {"chocobo", "Choco, Seeker of Paradise", "Legendary Creature — Bird"},
  {"chocobo", "Traveling Chocobo", "Creature — Bird"},
  {"chocobo", "Chocobo Camp", "Land — Town"},
  {"chocobo", "Black Chocobo", "Creature — Bird"},
}
for _, caller in ipairs(callers) do
  local track, name = caller[1], caller[2]
  data.White.playmat.objects = {card(caller[3], name)}; czmTick()
  check(playing and CZM.track == track and MusicPlayer.repeat_track, name .. " loops " .. track)
  local selectedLoads = loads
  advance(3); czmTick()
  check(loads == selectedLoads, track .. " remains one instance without restarting")
  Turns.turn_color = "Red"; onPlayerTurn(Player.Red, Player.White)
  check(not playing and czmBlocksVoice(), track .. " pauses outside its owner's turn and blocks voices")
  Turns.turn_color = "White"; onPlayerTurn(Player.White, Player.Red)
  check(playing and loads == selectedLoads, track .. " resumes unchanged on its owner's turn")
  data.White.playmat.objects = {}; czmTick()
end
check(CZM.cards.omega and CZM.omega:find("ff14_omega.wav", 1, true), "Omega has its own track")
check(CZM.chocobo:find("ff11_chocobo.wav", 1, true) and CZM.priority[#CZM.priority] == "chocobo",
  "Dash de Chocobo is its own track, last in priority")
-- Birds of Paradise and other non-Chocobo birds do not call it.
data.White.playmat.objects = {card("Creature — Bird", "Birds of Paradise")}; czmTick()
check(not playing, "Birds of Paradise calls nothing")
-- Any other song beats Chocobo on the same battlefield.
data.White.playmat.objects = {card("Legendary Creature — Bird", "Choco, Seeker of Paradise"),
                              card("Legendary Creature — God", "Ultima, Origin of Oblivion")}
czmTick(); check(playing and CZM.track == "ultima", "Ultima beats Chocobo")
data.White.playmat.objects = {}; czmTick()

-- The front faces of double-faced cards do not call their back face's song.
for _, name in ipairs({"Emet-Selch, Unsundered", "Crystal Fragments", "Jill, Shiva's Dominant"}) do
  data.White.playmat.objects = {card("Legendary Creature", name)}; czmTick()
  check(not playing, name .. " (front face) calls nothing")
end
-- Full "Front // Back" names, markup and curly apostrophes still match.
for _, name in ipairs({"Emet-Selch, Unsundered // Hades, Sorcerer of Eld", "[b]Summon: Titan[/b]",
                       "Clive, Ifrit\226\128\153s Dominant"}) do
  data.White.playmat.objects = {card("Legendary Creature", name)}; czmTick()
  check(playing, name .. " is recognised")
  data.White.playmat.objects = {}; czmTick()
end
-- Generic Summons, other Ifrits and other Omegas are not on the list.
for _, name in ipairs({"Summon: Fenrir", "Summon: G.F. Ifrit", "Omega Myr", "Titan of Industry"}) do
  data.White.playmat.objects = {card("Creature", name)}; czmTick()
  check(not playing, name .. " calls nothing")
end

-- Attached cards and the top of a face-up pile count; buried pile cards do not.
local host = card("Creature — Human", "Host"); host.attachments = {{name = "Summon: Titan\nSaga"}}
data.White.playmat.objects = {host}; czmTick()
check(playing and CZM.track == "titan", "an attached caller counts")
data.White.playmat.objects = {{type = "Deck", getObjects = function() return {
  {name = "Treasure\nArtifact"}, {name = "Summon: Titan\nSaga"}} end}}
czmTick()
check(not playing, "a caller buried in a face-up pile does not count")

-- Several callers at once: the first in CZM.priority wins, peeled off in order.
data.White.playmat.objects = {}
local order = {}
for _, track in ipairs(CZM.priority) do
  order[#order + 1] = track
  table.insert(data.White.playmat.objects, card("Creature", CZM.cards[track][1]))
end
for _, track in ipairs(order) do
  czmTick()
  check(playing and CZM.track == track, "priority chooses " .. track .. " before the remaining callers")
  table.remove(data.White.playmat.objects, 1)
end
czmTick(); check(not playing, "no callers left pauses playback")

-- A higher-priority caller can replace a loading track. Old callbacks never play.
MusicPlayer.loaded = false
data.White.playmat.objects = {card("Creature", "Clive, Ifrit's Dominant")}
czmTick(); local ifritWait = waits[#waits]
table.insert(data.White.playmat.objects, card("Creature", "Summon: Titan"))
czmTick(); local titanWait = waits[#waits]
local beforeStale = plays
ifritWait.fn()
check(CZM.track == "titan" and CZM.status == "loading" and plays == beforeStale, "superseded load cannot play a lower-priority track")
MusicPlayer.loaded = true; titanWait.fn()
check(playing and CZM.track == "titan", "current highest-priority load starts once ready")

print(checks .. " music checks, 0 failed")
