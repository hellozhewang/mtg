-- Search the physical deck alphabetically without reading or changing its order.
local checks, failures = 0, 0
local function check(condition, message)
  checks = checks + 1
  if not condition then failures = failures + 1; print("FAIL: " .. message) end
end
local attrs = {}
UI = {
  setAttribute = function(id, key, value)
    attrs[id] = attrs[id] or {}; attrs[id][key] = value
  end,
  getAttribute = function(id, key) return (attrs[id] or {})[key] end,
}
local ticks, nextTick = {}, 0
Wait = {
  frames = function(fn) fn() end,
  time = function(fn) nextTick = nextTick + 1; ticks[nextTick] = fn; return nextTick end,
  stop = function(id) ticks[id] = nil end,
}
CZ = {seats = {"White", "Red", "Yellow", "Green", "Blue", "Purple"}}
Player = {}
for _, c in ipairs(CZ.seats) do
  Player[c] = {color = c, steam_id = c .. "-owner", getHandTransform = function()
    return {position = {x = 1, y = 2, z = 3}, rotation = {x = 0, y = 180, z = 0}}
  end}
end
local taken, dealt, objects = {}, {}, {}
function getObjectFromGUID(guid) return objects[guid] end
function getAllObjects() local out = {}; for _, obj in pairs(objects) do out[#out + 1] = obj end; return out end
local function deck(guid, contents)
  local obj = {type = "Deck", menus = {"Existing item"}, contents = contents}
  obj.getGUID = function() return guid end
  obj.getObjects = function() return obj.contents end -- deliberately returns the actual array
  obj.addContextMenuItem = function(label, callback) obj.menus[#obj.menus + 1] = label; obj.open = callback end
  obj.getData = function()
    local children = {}
    for _, card in ipairs(obj.contents) do
      children[#children + 1] = {GUID = card.guid, CardID = 100, Nickname = card.name}
    end
    return {ContainedObjects = children, CustomDeck = {["1"] = {FaceURL = "https://example.test/card.jpg", NumWidth = 1, NumHeight = 1}}}
  end
  obj.takeObject = function(params)
    taken[#taken + 1] = params
    check(params.index == nil and params.guid ~= nil, "take uses a GUID, never a deck position")
    for i, card in ipairs(obj.contents) do
      if card.guid == params.guid then
        table.remove(obj.contents, i)
        local result = {deal = function(count, color) dealt[#dealt + 1] = {guid = card.guid, color = color, count = count} end}
        params.callback_function(result)
        return result
      end
    end
    return nil
  end
  objects[guid] = obj
  return obj
end
local baseSpawns, baseDestroys, baseChanges = 0, 0, 0
function onObjectSpawn() baseSpawns = baseSpawns + 1 end
function onObjectDestroy() baseDestroys = baseDestroys + 1 end
function onPlayerChangeColor() baseChanges = baseChanges + 1 end
local a = deck("deck-a", {
  {guid = "z", name = "Zombie\nCreature — Zombie", index = 0},
  {guid = "b2", name = "beta", index = 1},
  {guid = "a", name = "Alpha", index = 2},
  {guid = "b1", name = "Beta", index = 3},
  {guid = "p", name = "100% [Fun]", index = 4},
})
objects.notDeck = {type = "Card"}
dofile("tts/cactuar_search.lua")
local function tick() ticks[CZS.ticker]() end
check(#a.menus == 2 and a.menus[1] == "Existing item" and a.menus[2] == "Inspect", "existing menus survive; Inspect attached")
onObjectSpawn(a)
check(#a.menus == 2 and baseSpawns == 1, "spawn is wrapped and the menu is not duplicated")
a.open("White")
local white, red = Player.White, Player.Red
local s = CZS.state.White
check(attrs.czs_panel_White.active == "True" and CZS.state.Red == nil, "only the opener gets a browser")
check(s.cards[1].name == "100% [Fun]" and s.cards[2].name == "Alpha" and s.cards[5].name == "Zombie", "case-insensitive A–Z and first-line card names")
check(s.cards[3].guid == "b1" and s.cards[4].guid == "b2", "equal names break ties by GUID, not library index")
check(a.contents[1].guid == "z" and a.contents[5].guid == "p" and #taken == 0, "opening doesn't change order or take any card")
for _, card in ipairs(s.cards) do check(card.index == nil, "no library indexes retained in UI metadata") end
check(attrs.czs_image_1_White.image == "https://example.test/card.jpg", "single-card textures can be previewed")
czsSearch(white, "BETA", "czs_query_White")
check(#s.shown == 2 and s.shown[1] == "b1", "live, case-insensitive name filter")
czsSearch(white, "% [", "czs_query_White")
check(#s.shown == 1 and s.shown[1] == "p", "Lua pattern characters are literal search text")
czsSearch(white, "nothing", "czs_query_White")
check(attrs.czs_empty_White.active == "True" and #s.shown == 0, "no matches has an empty state")
check(attrs.czs_image_1_White.image == "" and attrs.czs_name_1_White.text == "", "stale pictures and names are cleared")
czsClear(white)
check(s.query == "" and s.page == 1, "clear restores all cards and page one")
-- A shuffle reorders only the real deck, never the alphabetical display.
a.contents[1], a.contents[3] = a.contents[3], a.contents[1]
tick()
check(s.shown[2] == "a" and s.shown[5] == "z", "shuffle never changes the A–Z display")
check(a.contents[1].guid == "a" and a.contents[3].guid == "z", "refresh does not undo or alter the real shuffle")
-- Another player's callback cannot control the first player's private panel.
czsSearch(red, "Zombie", "czs_query_White")
check(s.query == "", "other colours cannot submit callbacks for a private panel")
a.open("Red")
czsSearch(red, "Zombie", "czs_query_Red")
check(CZS.state.Red.shown[1] == "z" and #s.shown == 5, "simultaneous searches are independent")
check(attrs.czs_card_3_White.onClick == "czsPick(b1)", "client callback binds a card GUID, not a mutable slot")
czsPick(white, "b1", "czs_card_3_White")
check(s.selected == "b1" and attrs.czs_preview_White.active == "True", "selection previews the exact duplicate")
czsTake(white)
check(dealt[#dealt].guid == "b1" and dealt[#dealt].color == "White", "takes the selected physical card into the opener's hand")
check(#a.contents == 4 and a.contents[1].guid == "a" and a.contents[3].guid == "z", "taking a card leaves the other cards in order")
check(s.busy == false and s.selected == nil, "successful take clears selection and busy state")
-- A stale slot may not be reinterpreted as the next card after somebody draws.
czsPick(red, "z", "czs_card_1_Red")
for i, card in ipairs(a.contents) do if card.guid == "z" then table.remove(a.contents, i); break end end
local old = #taken
czsTake(red)
check(#taken == old and CZS.state.Red.selected == nil, "a removed selected GUID can't turn into a different draw")
-- Paging clamps after a shrinking deck and resets after filtering.
local many = {}
for i = 1, 28 do many[#many + 1] = {guid = string.format("g%03d", i), name = string.format("Card %02d", i), index = 28 - i} end
local big = deck("big", many)
onObjectSpawn(big); big.open("White"); s = CZS.state.White
czsPage(white, "next"); czsPage(white, "next")
check(s.page == 3 and #s.shown == 4, "gallery pages through the full deck")
local lateGuid = s.shown[1]
czsPage(white, "prev")
czsPick(white, lateGuid, "czs_card_1_White")
check(s.selected == nil, "a late callback from another page cannot select the new slot occupant")
czsPage(white, "next")
for i = #many, 8, -1 do table.remove(many, i) end
tick()
check(s.page == 1 and #s.shown == 7, "drawing cards clamps a now-empty final page")
czsSearch(white, "Card 0")
check(s.page == 1, "search resets the page")
-- Atlas imports still list and retrieve exact cards, without an incorrect sheet preview.
big.getData = function() return {ContainedObjects = {{GUID = "g001", CardID = 100}},
  CustomDeck = {["1"] = {FaceURL = "https://example.test/sheet.jpg", NumWidth = 10, NumHeight = 7}}} end
czsRefreshClick(white)
check(attrs.czs_image_1_White.image == "", "an atlas isn't displayed as a single card")
-- Destroying/collapsing a deck closes the browser and clears private contents.
onObjectDestroy(big); objects.big = nil
check(baseDestroys == 1 and CZS.state.White == nil and attrs.czs_panel_White.active == "False", "destroy wrapper closes the browser and preserves the original handler")
check(attrs.czs_name_1_White.text == "", "closed view does not leave another player's names behind")
local accented = deck("accents", {{guid = "e", name = "Éowyn, Shieldmaiden"},
  {guid = "z2", name = "Zulaport Cutthroat"}, {guid = "ae", name = "Æther Vial"}})
onObjectSpawn(accented); accented.open("White")
check(CZS.state.White.cards[1].guid == "ae" and CZS.state.White.cards[2].guid == "e", "accented MTG names sort with their base letters")
czsSearch(white, "EOWYN")
check(CZS.state.White.shown[1] == "e", "unaccented search finds an accented card")
accented.getData = function() return {ContainedObjects = {{GUID = "e", CardID = 100,
  CustomDeck = {["1"] = {NumWidth = 1, NumHeight = 1,
  FaceURL = "https://cards.scryfall.io/large/front/a/b/card.jpg?123"}}}}} end
czsRefreshClick(white)
check(attrs.czs_image_1_White.image == "https://img.klrmngr.com/display/front/a/b/card.webp", "old Scryfall image URLs use the existing TTS-compatible image host")
Player.Red.steam_id = "new-player"
onPlayerChangeColor("Red")
check(CZS.state.Red == nil and attrs.czs_panel_Red.active == "False", "changing players clears the previous player's search")
check(baseChanges == 1, "seat-change wrapper preserves the table's handler")
-- Live reload keeps one context item and one polling loop.
local menus, oldTicker = #a.menus, CZS.ticker
dofile("tts/cactuar_search.lua")
check(#a.menus == menus and ticks[oldTicker] == nil, "reloading duplicates neither menus nor pollers")
print(string.format("%d checks, %d failed", checks, failures))
os.exit(failures == 0 and 0 or 1)
