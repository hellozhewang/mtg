-- Search the physical deck alphabetically without reading or changing its order.
local checks, failures = 0, 0
local function check(condition, message)
  checks = checks + 1
  if not condition then failures = failures + 1; print("FAIL: " .. message) end
end
local attrs = {}
local file = assert(io.open("tts/cactuar_search.xml")); local template = file:read("*a"); file:close()
local cell = assert(template:match("<!%-%- @CARD@ %-%->\n(.*)"))
local xml = '<Panel id="unrelated" text="A &amp; B"/><GridLayout id="czs_grid_White"></GridLayout>'
local rebuilds, assetLoads = 0, 0
local assets = {{name = "base", url = "https://example.test/base.png"}}
local function imageURL(id)
  local name = (attrs[id] or {}).image
  for _, asset in ipairs(assets) do if asset.name == name then return asset.url end end
  return ""
end
local function loadInspect()
  dofile("tts/cactuar_regex.lua")
  local f = assert(io.open("tts/cactuar_search.lua")); local source = f:read("*a"); f:close()
  source = source:gsub("@INSPECT_CELL@", function() return cell end)
  assert(load(source, "cactuar_search.lua"))()
end
UI = {
  getXml = function() return xml end,
  getCustomAssets = function() return assets end,
  setCustomAssets = function(value)
    check(value[1].name == "base", "registering Inspect faces preserves the base table's assets")
    assets, assetLoads = value, assetLoads + 1
  end,
  setXml = function(value, assets)
    check(assets == nil, "expanding the grid preserves the shared custom assets")
    xml, rebuilds = value, rebuilds + 1
  end,
  setAttribute = function(id, key, value)
    attrs[id] = attrs[id] or {}; attrs[id][key] = value
  end,
  getAttribute = function(id, key) return (attrs[id] or {})[key] end,
}
local ticks, nextTick, conditions = {}, 0, {}
Wait = {
  frames = function(fn) fn() end,
  condition = function(fn, condition)
    if condition() then fn() else conditions[#conditions + 1] = fn end
  end,
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
function Vector(x, y, z) return setmetatable({x = x, y = y, z = z}, {
  __add = function(a, b) return Vector(a.x + b.x, a.y + b.y, a.z + b.z) end}) end
function getObjectFromGUID(guid) return objects[guid] end
function getAllObjects() local out = {}; for _, obj in pairs(objects) do out[#out + 1] = obj end; return out end
local function deck(guid, contents)
  local obj = {type = "Deck", menus = {"Existing item"}, contents = contents}
  obj.getGUID = function() return guid end
  obj.getName = function() return "Live " .. guid end
  obj.getPosition = function() return Vector(10, 1, 20) end
  obj.getObjects = function() return obj.contents end -- deliberately returns the actual array
  obj.addContextMenuItem = function(label, callback) obj.menus[#obj.menus + 1] = label; obj.open = callback end
  obj.getData = function()
    local children = {}
    for _, card in ipairs(obj.contents) do
      children[#children + 1] = {GUID = card.guid, CardID = 100, Nickname = card.name,
        Description = card.description, States = card.states, Tags = card.tags,
        GMNotes = card.gm_notes, LuaScript = card.lua_script}
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
local hotkeys = {{label = "Existing key"}}
function addHotkey(label, fn, release) hotkeys[#hotkeys + 1] = {label = label, fn = fn, release = release} end
local baseSpawns, baseDestroys, baseChanges = 0, 0, 0
function onObjectSpawn() baseSpawns = baseSpawns + 1 end
function onObjectDestroy() baseDestroys = baseDestroys + 1 end
function onPlayerChangeColor() baseChanges = baseChanges + 1 end
local zoneEnters, zoneLeaves = 0, 0
function onObjectEnterZone(_, obj)
  zoneEnters = zoneEnters + 1
  obj.menus = {"Cascade for X", "Get Basic Plains"}
end
function onObjectLeaveZone(_, obj)
  zoneLeaves = zoneLeaves + 1
  obj.menus = {"Cascade for X", "Get Basic Plains"}
end
local a = deck("deck-a", {
  {guid = "z", name = "Zombie\nCreature — Zombie", index = 0},
  {guid = "b2", name = "beta", index = 1},
  {guid = "a", name = "Alpha", index = 2},
  {guid = "b1", name = "Beta", index = 3},
  {guid = "p", name = "100% [Fun]", index = 4},
})
objects.notDeck = {type = "Card"}
loadInspect()
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
check(imageURL("czs_image_1_White") == "https://example.test/card.jpg", "single-card textures can be previewed")
check(#hotkeys == 1, "automatic hover needs no added hotkey and preserves existing keys")
czsHover(white, "a", "czs_card_2_White")
check(attrs.czs_zoom_White.active == "True" and attrs.czs_zoom_name_White.text == "Alpha", "ordinary hover immediately enlarges the card without a key")
check(imageURL("czs_zoom_image_White") == "https://example.test/card.jpg" and s.selected == nil and #taken == 0, "zoom uses the existing face without selecting or taking an object")
czsHover(white, "b1", "czs_card_3_White")
czsUnhover(white, "a", "czs_card_2_White")
check(attrs.czs_zoom_White.active == "True" and attrs.czs_zoom_name_White.text == "Beta", "moving between cells updates zoom; a stale exit cannot hide it")
czsZoomKey("White", false); czsZoomKey("White", true)
check(attrs.czs_zoom_White.active == "True", "an old live-session hotkey cannot interfere with automatic hover")
czsUnhover(white, "b1", "czs_card_3_White")
check(attrs.czs_zoom_White.active == "False" and attrs.czs_zoom_image_White.image == "", "leaving the card immediately hides and clears the enlarged image")
tick()
check(attrs.czs_zoom_White.active == "False", "refresh away from a card doesn't display stale content")
czsHover(white, "z", "czs_card_5_White")
check(attrs.czs_zoom_name_White.text == "Zombie", "entering another cell shows its own face")
czsHover(red, "a", "czs_card_2_White")
czsUnhover(red, "z", "czs_card_5_White")
check(attrs.czs_zoom_name_White.text == "Zombie" and CZS.state.Red == nil, "another player's hover events cannot change a private zoom")
czsSearch(white, "BETA", "czs_query_White")
check(#s.shown == 2 and s.shown[1] == "b1", "live, case-insensitive name filter")
check(attrs.czs_zoom_White.active == "False" and s.hovered == nil, "filter changes clear hover so a reused slot cannot reveal a different object")
czsHover(white, "z", "czs_card_5_White")
check(attrs.czs_zoom_White.active == "False", "a stale enter from a filtered-out card is rejected")
check(assetLoads == 1, "typing does not reload shared UI assets")
czsSearch(white, "% [", "czs_query_White")
check(#s.shown == 1 and s.shown[1] == "p", "Lua pattern characters are literal search text")
czsSearch(white, "nothing", "czs_query_White")
check(attrs.czs_empty_White.active == "True" and #s.shown == 0, "no matches has an empty state")
check(attrs.czs_image_1_White.image == "" and attrs.czs_name_1_White.text == "", "stale pictures and names are cleared")
czsClear(white)
check(s.query == "" and #s.shown == 5, "clear restores all objects")
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
czsHover(white, "b1", "czs_card_3_White")
czsPick(white, "b1", "czs_card_3_White")
check(attrs.czs_zoom_White.active == "False" and s.previewOpen, "click preview suppresses the transient zoom")
check(s.selected == "b1" and attrs.czs_preview_White.active == "True", "selection previews the exact duplicate")
czsHover(white, "a", "czs_card_2_White")
check(attrs.czs_preview_White.active == "False" and attrs.czs_zoom_name_White.text == "Alpha" and not s.selected,
  "hovering another card dismisses the pinned preview and clears its retrieval target")
local beforeHoverTake = #taken
czsTake(white)
check(#taken == beforeHoverTake, "hover cannot retrieve the previously selected card")
czsPick(white, "b1", "czs_card_3_White")
czsTake(white)
check(dealt[#dealt].guid == "b1" and dealt[#dealt].color == "White", "takes the selected physical card into the opener's hand")
check(#a.contents == 4 and a.contents[1].guid == "a" and a.contents[3].guid == "z", "taking a card leaves the other cards in order")
check(s.busy == false and s.selected == nil, "successful take clears selection and busy state")
-- A stale slot may not be reinterpreted as the next card after somebody draws.
czsPick(red, "z", "czs_card_1_Red")
czsHidePreview(red); czsHover(red, "z", "czs_card_1_Red")
for i, card in ipairs(a.contents) do if card.guid == "z" then table.remove(a.contents, i); break end end
tick()
check(attrs.czs_zoom_Red.active == "False", "a card removed from the live deck disappears from hover zoom")
local old = #taken
czsTake(red)
check(#taken == old and CZS.state.Red.selected == nil, "a removed selected GUID can't turn into a different draw")
-- Every entry is in one scrolling view; larger containers expand the pool.
-- A large unrelated shared UI and another seat's grid must survive byte-for-byte.
local largePrefix = string.rep('<Panel text="Unrelated &amp; layout"/>', 12000)
local otherGrid = '<GridLayout id="czs_grid_Red"><Text text="Other private grid"/></GridLayout>'
xml = largePrefix .. xml .. otherGrid
local many = {}
for i = 1, 257 do many[#many + 1] = {guid = string.format("g%03d", i), name = string.format("Card %03d", i), index = 257 - i} end
local big = deck("big", many)
onObjectSpawn(big); big.open("White"); s = CZS.state.White
check(#s.shown == 257 and s.shown[257] == "g257", "the scrolling view includes every object beyond the initial cell pool")
check(CZS.capacity.White == 320 and rebuilds == 1, "a large container grows the pool once instead of truncating")
check(xml:sub(1, #largePrefix) == largePrefix and xml:sub(-#otherGrid) == otherGrid,
  "bounded grid replacement preserves the large shared prefix and another private grid exactly")
check(#assets == 2, "Inspect assets are bounded to open views instead of accumulating past containers")
check(xml:find('id="unrelated" text="A &amp; B"', 1, true) ~= nil, "pool expansion preserves unrelated XML and entity escaping")
check(xml:find('id="czs_card_320_White"', 1, true) ~= nil, "new cells come from the build's shared template")
check(attrs.czs_title_White.text == "Live big", "window title uses the live container name")
local lateGuid = s.shown[257]
czsSearch(white, "Card 001")
czsPick(white, lateGuid, "czs_card_257_White")
check(s.selected == nil, "a late callback from a filtered-out object cannot select a new occupant")
czsSearch(white, "")
for i = #many, 8, -1 do table.remove(many, i) end
tick()
check(#s.shown == 7 and attrs.czs_card_257_White.active == "False", "membership refresh hides removed objects throughout the scrolling view")
czsSearch(white, "Card 00")
check(#s.shown == 7 and rebuilds == 1, "typing filters the entire view without rebuilding the shared UI")
-- Closing/changing seats while Global UI is rebuilding must not reopen a stale
-- private panel when the engine finishes loading the new tree.
local huge = {}
for i = 1, 400 do huge[i] = {guid = "h" .. i, name = "Object " .. i} end
local delayed = deck("delayed", huge); onObjectSpawn(delayed)
UI.loading = true; delayed.open("White")
check(CZS.rebuilding and #conditions == 1, "pool expansion waits for asynchronous UI loading")
czsClose(white)
UI.loading = false; conditions[1](); conditions = {}
check(CZS.state.White == nil and attrs.czs_panel_White.active == "False", "a closed panel stays private and closed after a rebuild")
big.open("White")
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
check(imageURL("czs_image_1_White") == "https://cards.scryfall.io/large/front/a/b/card.jpg?123", "Inspect uses the contained object's actual image without catalog-specific rewrites")
local bag = deck("bag", {{guid = "blue", name = "Blue marker"}, {guid = "amber", name = "Amber marker"}})
bag.type = "Bag"
bag.getData = function() return {ContainedObjects = {
  {GUID = "blue", Name = "Custom_Token", CustomImage = {ImageURL = "https://example.test/blue.png"}},
  {GUID = "amber", Name = "Custom_Tile", CustomImage = {ImageURL = "https://example.test/amber.png"}},
}} end
onObjectSpawn(bag); bag.open("White")
check(CZS.state.White.cards[1].guid == "amber" and CZS.state.White.cards[2].guid == "blue", "a non-card bag is inspected alphabetically without a deck catalog")
check(imageURL("czs_image_1_White") == "https://example.test/amber.png", "non-card objects use their contained image data")
check(bag.contents[1].guid == "blue" and bag.contents[2].guid == "amber", "inspecting a bag preserves its actual order too")
czsPick(white, "amber", "czs_card_1_White")
local oldDeals = #dealt
czsTake(white)
check(taken[#taken].guid == "amber" and taken[#taken].position.x == 13 and #dealt == oldDeals, "a bag object is taken next to the bag, never dealt as a card")
-- Real imports can have empty GUIDs on every contained card. Preview those
-- without fabricating physical IDs, changing the deck, or exposing positions.
local anonymous = deck("anonymous", {{guid = "", name = "Zulu"}, {guid = "", name = "Alpha"}, {guid = "", name = "Alpha"}})
anonymous.getData = function()
  local children = {}
  for _, v in ipairs(anonymous.contents) do children[#children + 1] = {GUID = "", Nickname = v.name, CardID = v.name == "Alpha" and 100 or 200} end
  return {ContainedObjects = children, CustomDeck = {
    [1] = {NumWidth = 1, NumHeight = 1, FaceURL = "https://example.test/alpha.jpg"},
    [2] = {NumWidth = 1, NumHeight = 1, FaceURL = "https://example.test/zulu.jpg"}}}
end
onObjectSpawn(anonymous); anonymous.open("White"); s = CZS.state.White
check(#s.shown == 3 and s.cards[1].name == "Alpha" and s.cards[3].name == "Zulu", "empty GUIDs do not hide imported cards or duplicates")
check(imageURL("czs_image_1_White") == "https://example.test/alpha.jpg" and imageURL("czs_image_3_White") == "https://example.test/zulu.jpg", "GUID-less cards keep their own matching images")
local token = s.shown[1]
anonymous.contents[1], anonymous.contents[2] = anonymous.contents[2], anonymous.contents[1]
tick()
check(s.shown[1] == token and s.cards[1].index == nil, "anonymous preview tokens survive shuffle and do not encode deck positions")
czsHover(white, token, "czs_card_1_White")
check(attrs.czs_zoom_White.active == "True" and imageURL("czs_zoom_image_White") == "https://example.test/alpha.jpg", "GUID-less imports support automatic hover using stable preview identities")
czsPick(white, token, "czs_card_1_White")
check(attrs.czs_preview_White.active == "True" and attrs.czs_preview_take_White.interactable == "False", "GUID-less objects can be previewed but cannot trigger unsafe retrieval")
old = #taken; czsTake(white)
check(#taken == old, "even a forged retrieval callback cannot take an anonymous card by position")
Player.Red.steam_id = "new-player"
onPlayerChangeColor("Red")
check(CZS.state.Red == nil and attrs.czs_panel_Red.active == "False", "changing players clears the previous player's search")
check(attrs.czs_zoom_Red.active == "False" and attrs.czs_zoom_image_Red.image == "", "seat changes clear zoom images as well")
check(baseChanges == 1, "seat-change wrapper preserves the table's handler")
-- Search every public text field, independently of display names and deck order.
local textDeck = deck("text-deck", {
  {guid = "gamma", name = "Gamma\nLegendary Creature — Elf", description = "[b]Draw[/b] a card.\nPay 2 life.", tags = {"Engine"},
    gm_notes = "secret-unsearchable", lua_script = "script-unsearchable",
    states = {["2"] = {Nickname = "Night Side\nEnchantment", Description = "<b>Flying</b> and haste."}}},
  {guid = "alpha", name = "Alpha\nArtifact", description = "{T}: Add one mana.", tags = {"Mana"}},
  {guid = "beta", name = "Beta\nInstant", description = "Counter target spell."},
})
onObjectSpawn(textDeck); textDeck.open("White"); s = CZS.state.White
local originalOrder = table.concat({textDeck.contents[1].guid, textDeck.contents[2].guid, textDeck.contents[3].guid})
local function searchFor(query, expected)
  czsSearch(white, query, "czs_query_White")
  check(table.concat(s.shown, ",") == expected, "full-text query: " .. query)
end
searchFor("creature", "gamma")
searchFor("draw a card", "gamma")
searchFor("ENGINE", "gamma")
searchFor("enchantment", "gamma")
searchFor("flying and haste", "gamma")
searchFor("{T}", "alpha")
searchFor("2 life", "gamma")
searchFor("secret-unsearchable", "")
searchFor("script-unsearchable", "")
searchFor("creature|artifact", "")
czsToggleRegex(red, nil, "czs_regex_White")
check(not s.regex, "other players cannot change the search mode of a private view")
czsToggleRegex(white, nil, "czs_regex_White")
check(s.regex and table.concat(s.shown, ",") == "alpha,gamma", "regex mode searches all text with alternation")
searchFor("draw.*card", "gamma")
searchFor("\\belf\\b", "gamma")
searchFor("^alpha$", "alpha")
searchFor("^\\D+$", "alpha,beta,gamma")
searchFor("\\d+ life", "gamma")
searchFor("(instant|artifact)", "alpha,beta")
searchFor("[", "")
check(attrs.czs_empty_White.text:find("Unclosed", 1, true) ~= nil, "invalid regex gives a visible error")
searchFor("counter", "beta")
check(attrs.czs_count_White.text:find("Regex", 1, true) ~= nil, "valid regex recovers after an error and labels its mode")
textDeck.contents[3].description = "Exile target creature."
tick()
check(#s.shown == 0, "editing description refreshes current matches without a membership change")
searchFor("exile", "beta")
czsToggleRegex(white, nil, "czs_regex_White")
searchFor("[b]", "")
check(table.concat({textDeck.contents[1].guid, textDeck.contents[2].guid, textDeck.contents[3].guid}) == originalOrder,
  "literal and regex searches never reorder the physical deck")
-- getObjects-only containers still expose descriptions when serialization is unavailable.
textDeck.getData = function() error("no serialized data") end
searchFor("exile", "beta")
-- Empty-GUID imports use serialized descriptions and types as well as names.
anonymous.getData = function()
  return {ContainedObjects = {
    {GUID = "", Nickname = "Zulu\nInstant", Description = "Destroy target permanent.", CardID = 200},
    {GUID = "", Nickname = "Alpha\nCreature — Elf", Description = "Draw a card.", CardID = 100},
    {GUID = "", Nickname = "Alpha\nCreature — Elf", Description = "Draw a card.", CardID = 100}},
    CustomDeck = {[1] = {FaceURL = "https://example.test/alpha.jpg"}, [2] = {FaceURL = "https://example.test/zulu.jpg"}}}
end
anonymous.open("White"); s = CZS.state.White
czsSearch(white, "draw a card", "czs_query_White")
check(#s.shown == 2, "serialized rules text is searchable for GUID-less duplicates")
-- Live reload keeps one context item and one polling loop.
local menus, oldTicker = #a.menus, CZS.ticker
loadInspect()
check(#a.menus == menus and ticks[oldTicker] == nil, "reloading duplicates neither menus nor pollers")
check(#hotkeys == 1, "live reload neither adds Inspect hotkeys nor clears existing bindings")
-- A full Global/browser reload resets native menus but may preserve object refs.
local previousBrowser = CZ
for _, obj in pairs(objects) do if obj.menus then obj.menus = {"Existing item"} end end
CZ = {seats = previousBrowser.seats}
loadInspect()
check(#a.menus == 2 and a.menus[2] == "Inspect", "full browser reload reattaches Inspect after native menus reset")
local afterReload = #a.menus
loadInspect()
check(#a.menus == afterReload, "an Inspect-only hot patch in the same browser still avoids duplicates")

-- A newly merged/split stack can report Card until the spawn frame finishes.
local fresh = deck("new-stack", {})
fresh.type = "Card"
local originalFrames, pendingFrames = Wait.frames, {}
Wait.frames = function(fn) pendingFrames[#pendingFrames + 1] = fn end
onObjectSpawn(fresh)
check(#fresh.menus == 1, "an unready stack is not marked attached")
fresh.type = "Deck"
for _, fn in ipairs(pendingFrames) do fn() end
Wait.frames = originalFrames
check(#fresh.menus == 2 and CZS.attached["new-stack"] == fresh, "the delayed spawn retry attaches once the deck exists")
local transient = deck("retry-menu", {})
local add, attempts = transient.addContextMenuItem, 0
transient.addContextMenuItem = function(...)
  attempts = attempts + 1
  if attempts == 1 then error("Native menu not ready") end
  return add(...)
end
onObjectSpawn(transient)
check(attempts == 2 and #transient.menus == 2, "failed native registration is retried without leaving a stale attached flag")

-- The real base clears custom menus on zone enter/leave. Restore after each event.
local library = {}
for i = 1, 3 do
  onObjectEnterZone(library, a)
  check(#a.menus == 3 and a.menus[3] == "Inspect", "zone entry restores Inspect after the base recreates its menu")
  onObjectLeaveZone(library, a)
  check(#a.menus == 3 and a.menus[3] == "Inspect", "zone exit restores Inspect without duplicates")
end
check(zoneEnters == 3 and zoneLeaves == 3, "original zone handlers still execute once per event")
check(a.menus[1] == "Cascade for X" and a.menus[2] == "Get Basic Plains", "base actions survive Inspect restoration")

print(string.format("%d checks, %d failed", checks, failures))
os.exit(failures == 0 and 0 or 1)
