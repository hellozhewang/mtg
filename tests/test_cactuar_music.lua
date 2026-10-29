-- Battle choruses called by named cards on the active player's battlefield, once
-- per turn, and the looping prelude, with real turn hooks.
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
local function advance(seconds)
  now = now + seconds
  if playing then position = position + seconds end
  if playing and not MusicPlayer.repeat_track and position >= 10 then playing = false end  -- a clip ends
end
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
-- A later turn of the same player, after the last chorus ended: every song can play again.
local function nextTurn() advance(11); CZM.turnSerial = CZM.turnSerial + 1; czmTick() end

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
check(CZM.battlefields.White.ultima == 1 and current.url:find("ff14_ultima.wav", 1, true) and playing
  and not MusicPlayer.repeat_track, "Ultima, Origin of Oblivion on the battlefield plays the Ultima chorus once")
check(#playlist == 1 and playlist[1].url == current.url, "Ultima replaces every previous playlist entry")
local ultimaLoads = loads
advance(3); czmTick()
check(position == 3 and loads == ultimaLoads and czmBlocksVoice(), "a chorus plays through without restarting, holding off turn clips")
advance(8); czmTick()
check(not playing and loads == ultimaLoads and not czmBlocksVoice(), "it ends after 10 seconds and is not replayed that turn")
Turns.turn_color = "Red"; onPlayerTurn(Player.Red, Player.White)
check(baseTurns == 1 and current.url:find("change-turn", 1, true) and loads == ultimaLoads + 1,
  "a turn without a caller gets the turn sound; the base handler still runs")
Turns.turn_color = "White"; onPlayerTurn(Player.White, Player.Red)
check(playing and current.url:find("ff14_ultima.wav", 1, true) and CZT.audioStatus == "suppressed for soundtrack",
  "the caller's owner's next turn plays the chorus again, ahead of the turn sound")
local whiteLoads = loads
advance(4); populate("Red", true)
Turns.turn_color = "Red"; onPlayerTurn(Player.Red, Player.White)
check(playing and position == 0 and loads == whiteLoads + 1, "a new turn cuts off the last chorus and plays the new player's from the top")
populate("Red", false); onObjectLeaveScriptingZone(data.Red.playmat, nil); flush()
check(playing and CZM.battlefields.Red.ultima == 0, "a caller leaving lets its chorus finish")
check(CZM.battlefields.White.ultima == 1, "another player's Ultima does not play on the wrong turn")
local redLoads = loads
populate("Red", true); onObjectEnterScriptingZone(data.Red.playmat, nil); flush()
check(loads == redLoads and baseEnters == 1, "the same caller returning that turn is not replayed; the base zone event still runs")
table.insert(data.Red.playmat.objects, card("Enchantment Creature — Saga Giant", "Summon: Titan")); czmTick()
check(playing and CZM.track == "titan" and position == 0 and loads == redLoads + 1, "a higher-priority caller landing mid-turn plays its own chorus")
table.remove(data.Red.playmat.objects); czmTick()
check(CZM.track == "titan" and loads == redLoads + 1, "losing it does not bring back a lower chorus that turn")
onChat("announcer test", Player.Red)
check(loads == redLoads + 1, "slow-turn test voices cannot overwrite a chorus still playing")
onChat("music off", Player.Red)
check(not playing, "music off stops the chorus")
onChat("music on", Player.Red)
check(not playing and loads == redLoads + 1 and baseChats >= 3, "music on does not replay a chorus heard this turn; chat handlers still run")
Turns.enable = false; nextTurn()
check(not playing, "no turns, no chorus")
Turns.enable = true; nextTurn()
check(playing and CZM.track == "ultima", "turns back on: the next turn plays it")

-- A live script patch must not restart a playing chorus or leave a second ticker.
local oldTicker, reloadLoads = CZM.ticker, loads
dofile("tts/cactuar_music.lua"); czmTick()
check(timers[oldTicker] == nil and loads == reloadLoads and playing, "live reload keeps the chorus and replaces its old ticker")

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

-- The card may leave while Ultima downloads: then it does not play, and was never
-- heard, so the card coming back that turn still gets it.
populate("Red", true); czmTick()
local ultimaWait = waits[#waits]
populate("Red", false); MusicPlayer.loaded = true; ultimaWait.fn()
check(not playing and CZM.status == "idle", "a chorus whose caller left while it loaded does not play")
populate("Red", true); czmTick()
check(playing and CZM.track == "ultima", "the caller coming back that turn still gets its chorus")
local ultimaCard = data.Red.playmat.objects[#data.Red.playmat.objects]
ultimaCard.nickname = "Changed face\nCreature — Human"
onObjectStateChange(ultimaCard, "old"); flush()
check(CZM.battlefields.Red.ultima == 0, "flipping the card to another face stops counting it")

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
data.White.playmat.objects = {}; nextTurn()
data.White.playmat.objects = {inHand}; Player.White.hands[1] = {inHand}; czmTick()
check(not playing and CZM.battlefields.White.thordan == 0, "a caller in hand does not play its song")
Player.White.hands[1] = {}; Player.White.hands[2] = {inHand}; czmTick()
check(not playing, "the second hand zone counts as hand too")
Player.White.hands[2] = {}; inHand.held_by_color = "White"; czmTick()
check(not playing, "a caller being dragged does not play its song")
inHand.held_by_color = nil; czmTick()
check(playing and CZM.track == "thordan", "the same card played onto the battlefield does")
data.White.playmat.objects = {}; nextTurn()

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
  data.White.playmat.objects = {}; nextTurn()
  data.White.playmat.objects = {card(caller[3], name)}; czmTick()
  check(playing and CZM.track == track and not MusicPlayer.repeat_track, name .. " plays the " .. track .. " chorus once")
  local selectedLoads = loads
  advance(3); czmTick()
  check(loads == selectedLoads and czmBlocksVoice(), track .. " is one instance, holding off turn clips")
  advance(8); czmTick()
  check(not playing and loads == selectedLoads, track .. " ends after 10 seconds without replaying")
  Turns.turn_color = "Red"; nextTurn()
  check(not playing, track .. " does not play on another player's turn")
  Turns.turn_color = "White"
end
check(CZM.cards.omega and CZM.omega:find("ff14_omega.wav", 1, true), "Omega has its own track")
check(CZM.chocobo:find("ff11_chocobo.wav", 1, true) and CZM.priority[#CZM.priority] == "chocobo",
  "Dash de Chocobo is its own track, last in priority")
-- Birds of Paradise and other non-Chocobo birds do not call it.
data.White.playmat.objects = {}; nextTurn()
data.White.playmat.objects = {card("Creature — Bird", "Birds of Paradise")}; czmTick()
check(not playing, "Birds of Paradise calls nothing")
-- Any other song beats Chocobo on the same battlefield.
data.White.playmat.objects = {card("Legendary Creature — Bird", "Choco, Seeker of Paradise"),
                              card("Legendary Creature — God", "Ultima, Origin of Oblivion")}
czmTick(); check(playing and CZM.track == "ultima", "Ultima beats Chocobo")
data.White.playmat.objects = {}; nextTurn()

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
  data.White.playmat.objects = {}; nextTurn()
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
data.White.playmat.objects = {}; nextTurn()
data.White.playmat.objects = {{type = "Deck", getObjects = function() return {
  {name = "Treasure\nArtifact"}, {name = "Summon: Titan\nSaga"}} end}}
czmTick()
check(not playing, "a caller buried in a face-up pile does not count")

-- Several callers at once: the first in CZM.priority wins. Mid-turn, each caller
-- that outranks everything heard so far plays; losing the top one plays nothing.
data.White.playmat.objects = {}; nextTurn()
for i = #CZM.priority, 1, -1 do
  local track = CZM.priority[i]
  table.insert(data.White.playmat.objects, card("Creature", CZM.cards[track][1])); czmTick()
  check(playing and CZM.track == track and position == 0, "a higher-priority " .. track .. " landing mid-turn plays")
end
local allLoads = loads
table.remove(data.White.playmat.objects); czmTick()
check(CZM.track == CZM.priority[1] and loads == allLoads, "losing the top caller does not play a lower one that turn")
table.insert(data.White.playmat.objects, card("Creature", CZM.cards[CZM.priority[1]][1])); nextTurn()
check(playing and CZM.track == CZM.priority[1], "with every caller out, a new turn plays the first in priority")
data.White.playmat.objects = {}; nextTurn()

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

-- The Sound switch: one table-wide setting for every Cactuar sound, music and turn clips.
local shown = {}
local switch = {call = function(fn, on) shown[#shown + 1] = on end}
czmRegister({object = switch}); czmRegister({object = switch})
check(#CZM.switches == 1 and shown[#shown] == true, "a switch registers once and shows sound on")
czmToggleSound({by = "Red"})
check(CZM.disabled and not playing and shown[#shown] == false, "the switch silences the music and shows off")
local beforeClip = loads
CZT.audioStatus = "untouched"
onChat("turn sound test", Player.Red)
check(loads == beforeClip and CZT.audioStatus == "untouched", "sound off silences the turn clips too")
czmToggleSound({by = "Red"})
check(not CZM.disabled and shown[#shown] == true, "switching back on shows sound on")
onChat("sound off", Player.Red)
check(CZM.disabled and shown[#shown] == false, "sound off in chat moves the switch too")
onChat("sound on", Player.Red)

print(checks .. " music checks, 0 failed")
