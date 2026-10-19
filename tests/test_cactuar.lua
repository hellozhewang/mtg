-- Plays tts/cactuar.lua against stand-ins for Tabletop Simulator's API and the
-- real files build_site.py writes under docs/tts/. Run from the repo root:
--     lua tests/test_cactuar.lua
-- tests/test_cactuar_lua.py runs it as part of the suite when lua is installed.

local failures, checks = 0, 0
local function check(cond, what)
  checks = checks + 1
  if not cond then
    failures = failures + 1
    print("FAIL: " .. what)
  end
end

-- ---------- a small JSON decoder (Tabletop Simulator provides JSON.decode) ----------
local function decode(s)
  local i = 1
  local function ws() i = s:find("[^ \t\r\n]", i) or #s + 1 end
  local value
  local function str()
    local out, j = {}, i + 1
    while true do
      local c = s:sub(j, j)
      if c == '"' then i = j + 1; return table.concat(out) end
      if c == "\\" then
        local e = s:sub(j + 1, j + 1)
        local map = {n = "\n", t = "\t", r = "\r", b = "\b", f = "\f", ['"'] = '"', ["\\"] = "\\", ["/"] = "/"}
        if e == "u" then
          out[#out + 1] = utf8.char(tonumber(s:sub(j + 2, j + 5), 16)); j = j + 6
        else
          out[#out + 1] = map[e]; j = j + 2
        end
      else
        out[#out + 1] = c; j = j + 1
      end
    end
  end
  function value()
    ws()
    local c = s:sub(i, i)
    if c == "{" then
      local t = {}; i = i + 1; ws()
      if s:sub(i, i) == "}" then i = i + 1; return t end
      while true do
        ws(); local k = str(); ws(); i = i + 1
        t[k] = value(); ws()
        local d = s:sub(i, i); i = i + 1
        if d == "}" then return t end
      end
    elseif c == "[" then
      local t = {}; i = i + 1; ws()
      if s:sub(i, i) == "]" then i = i + 1; return t end
      while true do
        t[#t + 1] = value(); ws()
        local d = s:sub(i, i); i = i + 1
        if d == "]" then return t end
      end
    elseif c == '"' then return str()
    elseif s:sub(i, i + 3) == "true" then i = i + 4; return true
    elseif s:sub(i, i + 4) == "false" then i = i + 5; return false
    elseif s:sub(i, i + 3) == "null" then i = i + 4; return nil
    else
      local num = s:match("^-?%d+%.?%d*[eE]?[-+]?%d*", i)
      i = i + #num
      return math.tointeger(tonumber(num)) or tonumber(num)
    end
  end
  return value()
end
JSON = {decode = decode}

local function read(path)
  local f = assert(io.open(path, "rb"))
  local text = f:read("a"); f:close()
  return text
end

-- ---------- stand-ins for the Tabletop Simulator API ----------
-- Tabletop Simulator ignores UI.setValue on a <Button>: its label is the "text"
-- attribute. So setValue on any Button id in tts/cactuar.xml is a failure.
local buttons = {}
for id in read("tts/cactuar.xml"):gmatch('<Button id="([^"]+)"') do
  buttons[#buttons + 1] = "^" .. id:gsub("{C}", "%%a+"):gsub("{I}", "%%d+") .. "$"
end
check(#buttons >= 9, "the stub knows the Buttons (" .. #buttons .. ")")
local function isButton(id)
  for _, pattern in ipairs(buttons) do
    if id:match(pattern) then return true end
  end
  return false
end
local attrs, values = {}, {}
UI = {
  setValue = function(id, v)
    check(not isButton(id), "setValue on Button " .. id .. ": label it with setAttribute text")
    check(not v:find("[<&]"), "raw XML text breaks the importer's UI rebuild: " .. id)
    values[id] = v
  end,
  setAttribute = function(id, k, v)
    attrs[id] = attrs[id] or {}; attrs[id][k] = v
    if k == "text" then values[id] = v end
  end,
  getAttribute = function(id, k) return (attrs[id] or {})[k] end,
  -- Custom assets: the base table's own, which setCustomAssets must keep.
  assets = {{name = "base_logo", url = "https://example.test/logo.png"}},
  assetCalls = 0,
  loading = false,
}
function UI.getCustomAssets() return UI.assets end
function UI.setCustomAssets(list) UI.assets = list; UI.assetCalls = UI.assetCalls + 1 end
local requests = 0
local legacySize, legacyQuery, expectedObjects, rewrittenImages
WebRequest = {get = function(url, cb)
  requests = requests + 1
  local path = "docs/tts/" .. url:gsub("^test://tts/", ""):gsub("%?.*$", "")
  local ok, text = pcall(read, path)
  if ok and path:match("%.ndjson$") then
    expectedObjects, rewrittenImages = {}, 0
    for line in text:gmatch("[^\n]+") do expectedObjects[#expectedObjects + 1] = line end
    if legacySize then
      -- Reproduce the files still live on Pages before the exporter fix.
      text, rewrittenImages = text:gsub(
        '("FaceURL"%s*:%s*")https://img%.klrmngr%.com/display/([^"]+)%.webp"',
        function(prefix, face)
          return prefix .. "https://cards.scryfall.io/" .. legacySize .. "/" .. face .. ".jpg" .. (legacyQuery or "") .. '"'
        end)
    end
  end
  cb({is_error = not ok, error = ok and nil or "404", text = ok and text or ""})
end}
local spawned, broadcasts, shuffled = {}, {}, 0
function spawnObjectJSON(p)
  spawned[#spawned + 1] = p
  if p.callback_function then p.callback_function({shuffle = function() shuffled = shuffled + 1 end}) end
end
function broadcastToAll(msg) broadcasts[#broadcasts + 1] = msg end
function broadcastToColor(msg, color) broadcasts[#broadcasts + 1] = color .. ": " .. msg end
local function obj(name, x, z)
  return {getName = function() return name end, getPosition = function() return {x = x, y = 1, z = z} end}
end
local inZone = {}
local seats = {
  {color = "White", x = 41.8, forward = 1}, {color = "Red", x = 12.4, forward = 1},
  {color = "Yellow", x = -17.0, forward = 1}, {color = "Green", x = -41.8, forward = -1},
  {color = "Blue", x = -12.4, forward = -1}, {color = "Purple", x = 17.1, forward = -1},
}
function getAllObjects()
  local objects = {}
  for _, seat in ipairs(seats) do
    objects[#objects + 1] = obj("Life Tracker", seat.x, -5.7 * seat.forward)
    objects[#objects + 1] = obj("Commander Zone", seat.x, -13.4 * seat.forward)
    objects[#objects + 1] = obj("Commander Zone", seat.x, -9.6 * seat.forward)
  end
  -- A farther unrelated zone is inside the search radius: select the own pair
  -- before ordering it, rather than taking the two farthest candidates.
  objects[#objects + 1] = obj("Commander Zone", 41.8, -2)
  return objects
end
data = {}
for _, seat in ipairs(seats) do
  data[seat.color] = {libraryZone = {
    getPosition = function() return {x = seat.x, y = 2.46, z = -20.1 * seat.forward} end,
    getRotation = function() return {x = 0, y = seat.forward == 1 and 0 or 180, z = 0} end,
    getTransformForward = function() return {x = 0, y = 0, z = seat.forward} end,
    getTransformRight = function() return {x = seat.forward, y = 0, z = 0} end,
    getObjects = function() return inZone end,
  }}
end

-- Chat log, seat colours and player names for Tournament mode.
local logs = {}
function printToAll(msg) logs[#logs + 1] = msg end
Color = {fromString = function() return {r = 1, g = 1, b = 1} end}
Player = setmetatable({}, {__index = function(_, c) return {color = c, steam_name = c .. "Name"} end})
local waits = {}
Wait = {time = function(f) waits[#waits + 1] = f end,
        condition = function(f, ready) if ready() then f() else waits[#waits + 1] = f end end}
local function settle() local w = waits; waits = {}; for _, f in ipairs(w) do f() end end
local function logged(pattern)
  for _, l in ipairs(logs) do if l:find(pattern, 1, true) then return l end end
  return nil
end

-- ---------- load the browser ----------
local source = read("tts/cactuar.lua"):gsub("@BASE_URL@", "test://tts/")
assert(load(source, "cactuar.lua"))()
local white, grey = {color = "White", steam_name = "zz"}, {color = "Grey", steam_name = "spectator"}

-- A spectator cannot open it: decks load into your own seat.
czOpenFor({color = "Grey"})
check(broadcasts[1] and broadcasts[1]:find("Take a seat"), "spectator is told to sit")
check(attrs["cz_panel_Grey"] == nil, "no panel for a spectator")

-- Clicking a Cactuar tile fetches the index and fills the rows, newest first.
czOpenFor({color = "White"})
check(attrs["cz_panel_White"].active == "True", "panel opens")
check(CZ.index and #CZ.index.decks > 100, "index loaded")
local s = CZ.state.White
check(#s.list == #CZ.index.decks, "every deck listed")
check(s.sort == "newest", "newest is the default sort")
for k = 2, #s.list do
  check(s.list[k - 1].added >= s.list[k].added, "newest order at " .. k)
end
check(attrs["cz_sort_newest_White"].colors ~= attrs["cz_sort_tier_White"].colors, "Newest shows as the active sort")
check(not read("tts/cactuar.xml"):find("cz_sort_owner", 1, true), "no Owner sort button")
-- Reopening uses the list it has while it's fresh, and re-fetches an old one.
local before = requests
czOpenFor({color = "White"}); czOpenFor({color = "White"})       -- close, open
check(requests == before, "a fresh list isn't fetched again on open")
CZ.indexAt = os.time() - CZ.staleAfter - 1
czOpenFor({color = "White"}); czOpenFor({color = "White"})
check(requests == before + 1 and CZ.indexAt >= os.time() - 1, "an old list is fetched again on open")
check(attrs["cz_panel_White"].active == "True", "the panel is open after the re-fetch")
czSort(white, "owner")
check(s.sort == "newest", "an unknown sort is ignored")
czSort(white, "tier")
check(s.list[1].tier == "GOD", "tier sort puts GOD first (got " .. tostring(s.list[1].tier) .. ")")
check(values["cz_row_name_1_White"] == s.list[1].name, "row 1 shows the first deck")
check(attrs["cz_row_10_White"].active == "True", "a full first page")
check(values["cz_page_White"]:find("^Page 1 /"), "pager text")
check(values["cz_count_White"] == #CZ.index.decks .. " decks", "unfiltered collection count")
check(attrs["cz_prev_White"].interactable == "False", "no Previous on the first page")
check(attrs["cz_next_White"].interactable == "True", "Next available on a full collection")
check(attrs["cz_load_White"].interactable == "False", "Load disabled until a deck is selected")
check(values["cz_random_White"]:find("<color=#E2E5EA>", 1, true), "Random label retains contrast under importer Button defaults")

-- Sorting by name, then filtering by owner.
czSort(white, "name")
for k = 2, #s.list do
  check(s.list[k - 1].name:lower() <= s.list[k].name:lower(), "name order at " .. k)
end
czFilter(white, "owner")
check(attrs["cz_menu_White"].active == "True" and s.menu == "owner", "owner menu opens")
check(values["cz_choice_1_White"]:find("Owner: All", 1, true), "All is an explicit menu choice")
check(values["cz_choice_2_White"]:find("digitalstealth", 1, true), "direct owner choices")
czChoose(white, "2")
local owner = s.filter.owner
check(owner == "digitalstealth", "first owner alphabetically (got " .. tostring(owner) .. ")")
for _, d in ipairs(s.list) do check(d.owner == owner, "owner filter keeps only " .. owner) end
check(attrs["cz_f_owner_White"].text:find(owner, 1, true), "owner button shows the value")
check(attrs["cz_menu_White"].active == "False", "choosing a value dismisses the menu")
check(values["cz_count_White"] == #s.list .. " of " .. #CZ.index.decks .. " decks", "filtered count also shows collection total")
czClear(white)
check(next(s.filter) == nil and #s.list == #CZ.index.decks, "Clear resets filters")

-- Filter menus support direct choices, All, outside dismissal, and separate seats.
czFilter(white, "theme")
check(values["cz_choice_2_White"]:find("Aggro & Voltron", 1, true), "strategy labels retain ampersands in attributes")
czChoose(white, "2")
check(s.filter.theme == "aggro", "strategy chosen directly")
czFilter(white, "theme"); czChoose(white, "1")
check(s.filter.theme == nil, "All removes that filter")
czFilter(white, "tier"); czDismiss(white)
check(not s.menu and attrs["cz_scrim_White"].active == "False", "outside click dismisses menu")
czOpenFor({color = "Red"}); czFilter({color = "Red"}, "tier")
czFilter(white, "owner"); czChoose(white, "2")
check(CZ.state.Red.menu == "tier" and next(CZ.state.Red.filter) == nil, "menus and filters are per player")
czDismiss({color = "Red"}); czClear(white)

-- More owners than fit in one menu remain reachable, including the last page.
local originalDecks = CZ.index.decks
local extended = {}
for _, d in ipairs(originalDecks) do extended[#extended + 1] = d end
for i = 1, 21 do
  local d = {}
  for k, v in pairs(originalDecks[1]) do d[k] = v end
  d.id, d.owner = "extra-" .. i, string.format("owner%02d", i)
  extended[#extended + 1] = d
end
CZ.index.decks = extended
czRender("White"); czFilter(white, "owner")
check(attrs["cz_menu_pager_White"].active == "True", "long menus have pagination")
czMenuPage(white, "next"); czMenuPage(white, "next")
check(s.menuPage == 3, "last menu page reachable")
czChoose(white, "1")
check(s.filter.owner and #s.list > 0, "a choice on later pages applies")
czFilter(white, "owner")
check(s.menuPage == 3, "reopening keeps selected option visible")
CZ.index.decks = originalDecks
czClear(white)

-- Page bounds and empty states never offer stale actions or hide total counts.
czPage(white, "prev")
check(s.page == 1, "Previous cannot go before first page")
czSearch(white, "no-matching-deck-xyz")
check(#s.list == 0 and attrs["cz_empty_White"].active == "True", "empty search explains how to recover")
check(values["cz_count_White"] == "0 of " .. #CZ.index.decks .. " decks", "empty results keep collection total")
check(attrs["cz_next_White"].interactable == "False" and attrs["cz_random_White"].interactable == "False", "empty results disable Next and Random")
czClear(white)

-- Search, pick, load: Giada lands in White's seat.
czSearch(white, "giada")
check(#s.list >= 1 and s.list[1].name == "Giada-Angels", "search finds Giada")
czPick(white, "1")
check(s.selected and s.selected.name == "Giada-Angels", "picked Giada")
check(values["cz_detail_White"]:find("Giada, Font of Hope", 1, true), "detail shows the commander")
check(attrs["cz_load_White"].interactable == "True", "selection enables loading")
check(values["cz_lands_White"]:find(tostring(s.selected.lands), 1, true), "selected stats are shown")
czSearch(white, "akroma")
check(s.selected == nil and attrs["cz_load_White"].interactable == "False", "filtering out selection disables stale Load")
czSearch(white, "giada"); czPick(white, "1")

-- A pending load cannot be duplicated; an error restores the action and selection.
local originalGet, pendingLoad, pendingCount = WebRequest.get, nil, 0
WebRequest.get = function(url, callback) pendingLoad = callback; pendingCount = pendingCount + 1 end
czLoad(white); czLoad(white)
check(pendingCount == 1 and CZ.busy.White, "only one pending request per seat")
check(attrs["cz_load_White"].interactable == "False", "Load is disabled while fetching")
pendingLoad({is_error = true, error = "network down"})
check(not CZ.busy.White and attrs["cz_load_White"].interactable == "True", "failed request permits retry")
check(attrs["cz_status_White"].color == "#FF9A9A", "failed load is visibly an error")
WebRequest.get = originalGet
legacySize, legacyQuery = "large", "?1783926791"
czLoad(white)
check(rewrittenImages > 0, "the reply reproduced legacy Scryfall images")
check(#spawned == 3, "library, commander and tokens spawn (got " .. #spawned .. ")")
for i, obj in ipairs(spawned) do
  check(obj.json == expectedObjects[i + 1], "legacy large image repair preserves the complete object " .. i)
end
local library, commander, tokens = spawned[1], spawned[2], spawned[3]
check(library.position[1] == 41.8 and library.position[3] == -20.1, "library in the library zone")
check(library.rotation[3] == 180 and library.rotation[2] == 180, "library face down, facing the seat")
check(shuffled == 1, "library shuffled")
check(decode(library.json).Name == "DeckCustom" and #decode(library.json).ContainedObjects == 99, "99-card library")
check(commander.position[3] == -9.6 and commander.rotation[3] == 180, "single commander face down (hidden) in the first (upper) slot")
check(tokens.rotation[3] == 180, "tokens face down too")
check(decode(commander.json).Nickname:find("^Giada, Font of Hope"), "the commander is Giada")
-- The table's mulligan refuses while a card or deck is in the play area, which is
-- the mat left of the column: tokens stay in the column, on the free second slot.
check(tokens.position[1] == 41.8 and tokens.position[3] == -13.4, "a single commander's tokens go on the free second slot")
check((tokens.position[1] - 41.8) ^ 2 + (tokens.position[3] + 5.7) ^ 2 > 9, "tokens clear of the Life Tracker")
check(values["cz_status_White"] == "Loaded Giada-Angels.", "status for a deck with tokens")
check(broadcasts[#broadcasts] == "zz loaded a deck.", "the table is told a deck was loaded, not which (got " .. tostring(broadcasts[#broadcasts]) .. ")")
check(attrs["cz_panel_White"].active == "False", "panel closes after loading")

-- The tile toggles: a second click closes an open panel.
czOpenFor({color = "White"})
check(attrs["cz_panel_White"].active == "True", "tile opens the panel")
czOpenFor({color = "White"})
check(attrs["cz_panel_White"].active == "False", "a second click closes it")

-- A partner pair takes both Commander Zones.
spawned = {}
legacySize, legacyQuery = "normal", ""
czOpen(white); czSearch(white, "akroma"); czPick(white, "1"); czLoad(white)
check(rewrittenImages > 0, "the reply reproduced normal-size Scryfall images")
for i, obj in ipairs(spawned) do
  check(obj.json == expectedObjects[i + 1], "legacy normal image repair preserves the complete object " .. i)
end
check(#spawned >= 3, "partner deck spawns library and two commanders")
check(spawned[2].position[3] == -9.6 and spawned[3].position[3] == -13.4, "first commander in first slot, partner in second")
check(decode(spawned[3].json).Nickname:find("^Vial Smasher"), "the partner is Vial Smasher")

-- Already-correct exports pass through unchanged, including all CustomDeck keys.
spawned, legacySize = {}, nil
czLoad(white)
for i, obj in ipairs(spawned) do
  check(obj.json == expectedObjects[i + 1], "cached image JSON passes through unchanged " .. i)
end

-- Slot order is from the life tracker toward the library, for every seat.
for _, seat in ipairs(seats) do
  local player = {color = seat.color, steam_name = seat.color}
  spawned = {}
  czOpen(player); czClear(player); czSearch(player, "akroma"); czPick(player, "1"); czLoad(player)
  check(spawned[2].position[1] == seat.x and spawned[2].position[3] == -9.6 * seat.forward,
    seat.color .. ": first commander in first slot")
  check(decode(spawned[2].json).Nickname:find("^Akroma"), seat.color .. ": first commander stays Akroma")
  check(spawned[3].position[1] == seat.x and spawned[3].position[3] == -13.4 * seat.forward,
    seat.color .. ": second commander in second slot")
  check(decode(spawned[3].json).Nickname:find("^Vial Smasher"), seat.color .. ": second stays Vial Smasher")
  local t = spawned[#spawned].position
  check(t[1] == seat.x, seat.color .. ": tokens stay in the column, out of the play area")
  check(math.abs(t[3] - (-13.4 - 20.1) / 2 * seat.forward) < 0.001,
    seat.color .. ": partners fill both slots, so tokens go on the exile spot")
  check((t[1] - seat.x) ^ 2 + (t[3] + 5.7 * seat.forward) ^ 2 > 9, seat.color .. ": tokens clear of the Life Tracker")
end

-- A table with no Commander Zone objects keeps the same slot order in fallback positions.
local originalObjects = getAllObjects
getAllObjects = function() return {} end
spawned = {}
czLoad(white)
check(math.abs(spawned[2].position[3] - (-20.1 + 10.5)) < 0.001, "fallback first slot")
check(math.abs(spawned[3].position[3] - (-20.1 + 6.8)) < 0.001, "fallback second slot")
local t = spawned[#spawned].position
check(t[1] == 41.8 and t[3] < spawned[3].position[3] and t[3] > -20.1,
  "fallback tokens stay in the column, between the second slot and the library")
getAllObjects = originalObjects

-- A deck whose cards make no tokens spawns none, and says so.
spawned = {}
czOpen(white); czClear(white); czSearch(white, "beamtown"); czPick(white, "1"); czLoad(white)
check(#spawned == 2, "library and commander only, no token pile (got " .. #spawned .. ")")
check(values["cz_status_White"]:find("makes no tokens", 1, true), "the player is told there are no tokens")

-- The sleeves grid: Standard first, then the repo's sleeves as thumbnails; the choice
-- applies on load.
spawned = {}
czOpen(white); czClear(white)
check(attrs["cz_sleeve_White"].text:find("Sleeves: Standard", 1, true), "sleeves button starts on Standard")
check(attrs["cz_sleeve_White"].interactable == "True", "sleeves menu enabled when the repo has sleeves")
-- Thumbnails are registered once, next to the base table's own assets.
local names = {}
for _, a in ipairs(UI.assets) do names[a.name] = a.url end
check(names.base_logo, "the base table's assets are kept")
check(names.czsl_standard and names.czsl_standard:find("backs.scryfall.io/small/", 1, true), "Standard's thumbnail is Scryfall's small back")
check(names.czsl_cactuar and names.czsl_cactuar:match("^test://tts/sleeves/thumbs/cactuar%.jpg%?v=%x+$"), "repo sleeves use their published thumbnail")
local calls = UI.assetCalls
czRefresh(white)
check(UI.assetCalls == calls, "an unchanged list doesn't reload the UI")
czFilter(white, "sleeve")
check(s.menu == "sleeve" and attrs["cz_sleeves_White"].active == "True", "the sleeves grid opens")
check(attrs["cz_menu_White"].active ~= "True", "not the text menu")
check(values["cz_sl_name_1_White"] == "✓ Standard", "Standard listed first and ticked")
check(attrs["cz_sl_img_1_White"].image == "czsl_standard", "cells show their thumbnail")
local cactuarCell
for i, b in ipairs(CZ.index.sleeves) do
  if i > CZ.sleeveCells then break end
  check(values["cz_sl_name_" .. i .. "_White"]:find(b.label, 1, true), "sleeve " .. b.label .. " in order")
  if b.id == "cactuar" then cactuarCell = i end
end
local pages = math.ceil(#CZ.index.sleeves / CZ.sleeveCells)
check(attrs["cz_sleeves_pager_White"].active == (pages > 1 and "True" or "False"), "the pager shows only with more than one page")
check(values["cz_sleeves_page_White"] == "1 / " .. pages, "page count")
check(cactuarCell, "the repo's Cactuar sleeve is on page 1")
czSleevePick(white, tostring(cactuarCell))
check(s.sleeve == "cactuar" and attrs["cz_sleeves_White"].active == "False", "picking a thumbnail closes the grid")
check(attrs["cz_sleeve_White"].text:find("Sleeves: Cactuar", 1, true), "button shows the chosen sleeves")
check(next(s.filter) == nil and #s.list == #CZ.index.decks, "picking sleeves leaves the filters alone")
-- Paging: with more sleeves than one page, the grid pages and opens on the chosen one.
local realSleeves = CZ.index.sleeves
local many = {realSleeves[1]}
for i = 1, 19 do many[#many + 1] = {id = "s" .. i, label = "S" .. i, file = "sleeves/s" .. i .. ".jpg"} end
CZ.index.sleeves = many
czFilter(white, "sleeve")
check(values["cz_sleeves_page_White"] == "1 / 3" and attrs["cz_sleeves_pager_White"].active == "True", "20 sleeves are 3 pages")
check(attrs["cz_sl_img_2_White"].image == "", "a sleeve without a thumbnail shows its name only")
czMenuPage(white, "next"); czMenuPage(white, "next")
check(values["cz_sleeves_page_White"] == "3 / 3" and attrs["cz_sl_4_White"].active == "True" and attrs["cz_sl_5_White"].active == "False", "the last page holds the rest")
czSleevePick(white, "4")
check(s.sleeve == "s19", "picking on a later page picks that sleeve")
czFilter(white, "sleeve")
check(values["cz_sleeves_page_White"] == "3 / 3", "the grid reopens on the chosen sleeve's page")
czDismiss(white)
CZ.index.sleeves = realSleeves
czOpen(white); czFilter(white, "sleeve"); czSleevePick(white, tostring(cactuarCell)); czOpen(white)
czSearch(white, "giada"); czPick(white, "1"); czLoad(white)
local backs, faces = 0, 0
for i, o in ipairs(spawned) do
  for url in o.json:gmatch('"BackURL":"([^"]*)"') do
    backs = backs + 1
    check(url:match("^test://tts/sleeves/cactuar%.jpg%?v=%x+$") ~= nil, "every card gets the chosen back (" .. url .. ")")
  end
  local standard = o.json:gsub('"BackURL":"[^"]*"', '"BackURL":"https://backs.scryfall.io/large/0/a/0aeebaf5-8c7d-4636-9e82-8c27447861f7.jpg"')
  check(standard == expectedObjects[i + 1], "only BackURL changes in object " .. i)
end
check(backs > 50, "library, commander and token backs all swapped (" .. backs .. ")")
czOpen(white); czFilter(white, "sleeve"); czSleevePick(white, "1")
check(s.sleeve == "standard" and attrs["cz_sleeve_White"].text:find("Standard", 1, true), "Standard can be chosen again")
spawned = {}
czLoad(white)
for i, o in ipairs(spawned) do check(o.json == expectedObjects[i + 1], "Standard leaves object " .. i .. " untouched") end
check(CZ.state.Red == nil or CZ.state.Red.sleeve == nil, "each player has their own back")
local withBacks = CZ.index.sleeves
CZ.index.sleeves = nil                     -- a deck list published before sleeves
czRender("White")
check(attrs["cz_sleeve_White"].interactable == "False", "no sleeves list: the button is disabled")
czFilter(white, "sleeve")
check(s.menu == nil and attrs["cz_sleeves_White"].active ~= "True", "no sleeves list: the grid stays shut")
CZ.index.sleeves = withBacks

-- A new player in a seat gets a fresh browser, not the last player's leftovers.
local whoIn = {}
Player = setmetatable({}, {__index = function(_, c) return {color = c, steam_name = c .. "Name", steam_id = whoIn[c]} end})
whoIn.Purple = "kupo"
local purple = {color = "Purple", steam_name = "Kupo"}
czOpen(purple); czSearch(purple, "sheoldred"); czPick(purple, "1")
check(CZ.state.Purple.selected ~= nil and CZ.state.Purple.query == "sheoldred", "Kupo searched and picked in Purple")
czClose(purple)
whoIn.Purple = "em0k1ller"                                     -- Kupo moved; Em0k1ller sat down
czOpen({color = "Purple", steam_name = "Em0k1ller"})
check(CZ.state.Purple.selected == nil and CZ.state.Purple.query == "", "the new player starts with a clean browser")
check(attrs["cz_search_Purple"].text == "" and values["cz_status_Purple"] == "", "search box and status cleared")
czClose({color = "Purple"})
whoIn.Purple = nil
Player = setmetatable({}, {__index = function(_, c) return {color = c, steam_name = c .. "Name"} end})

-- ---------- Tournament mode ----------
spawned, inZone = {}, {}
czOpen(white); czClear(white)
logs = {}
czSearch(white, "zzz")
check(#logs == 0 and #waits == 0, "nothing is logged outside Tournament mode")
czClear(white)
local pool = CZ.index.tournament
check(#pool == 24, "the index carries the 24-deck tournament pool (" .. #pool .. ")")
check(attrs["cz_tour_White"].interactable == "True", "Tournament button enabled when there is a pool")
czTournament(white)
check(s.tour and s.tour.mode == "all", "Tournament mode starts on All pick")
check(logged("(White): entered tournament mode: All pick from 24 decks"), "entering is logged")
check(logged("[Tournament ") and logged("WhiteName (White)"), "log lines carry the tag, name and seat")
check(attrs["cz_filters_White"].active == "False" and attrs["cz_tourbar_White"].active == "True", "the mode row replaces the filters")
check(attrs["cz_tour_White"].text:find("Leave tournament", 1, true), "the button offers to leave")
check(#s.list == 24, "All pick lists exactly the pool (" .. #s.list .. ")")
local inPool = {}
for _, id in ipairs(pool) do inPool[id] = true end
for _, d in ipairs(s.list) do check(inPool[d.id], "only pool decks listed: " .. d.id) end
check(values["cz_count_White"] == "24 tournament decks", "count says tournament decks")
s.filter.owner = "kupo7"; czRender("White")
check(#s.list == 24, "hidden filters don't apply in Tournament mode")
s.filter = {}

-- Every action is logged: search (once it settles), sort, page, select, sleeves.
czSearch(white, "r"); czSearch(white, "re"); czSearch(white, "reanimator")
check(not logged('searched "re'), "typing isn't logged per keystroke")
settle()
local searches = 0
for _, l in ipairs(logs) do if l:find("searched the list", 1, true) then searches = searches + 1 end end
check(searches == 1 and not logged("reanimator"), "the settled search is logged once, without the search text")
check(#s.list >= 1 and #s.list < 24, "search narrows All pick")
czClear(white)
check(logged("reset the search"), "reset logged")
czSort(white, "name"); check(logged("sorted by Name"), "sort logged")
czPage(white, "next"); check(logged("turned to page 2"), "paging logged")
czPage(white, "prev")
czPick(white, "1"); check(s.selected and logged("selected a deck") and not logged(s.selected.name), "selection logged without the deck")
czFilter(white, "sleeve"); czSleevePick(white, "2")
check(logged("chose sleeves " .. CZ.index.sleeves[2].label), "sleeves choice logged")
czFilter(white, "sleeve"); czSleevePick(white, "1")

-- Draft: 5 different pool decks; Redraw deals again, logged with a count.
czTourMode(white, "draft")
local offer = s.tour.offer
check(#offer == 5 and #s.list == 5, "Draft offers 5")
local seen = {}
for _, d in ipairs(offer) do check(inPool[d.id] and not seen[d.id], "draft offer is distinct pool decks"); seen[d.id] = true end
check(logged("switched to Draft (5 decks dealt)"), "the dealt offer is logged, without its decks")
check(values["cz_count_White"] == "Draft: pick 1 of 5", "count explains the draft")
check(attrs["cz_tredraw_White"].active == "True" and attrs["cz_tredraw_White"].text:find("Redraw", 1, true), "Redraw shown in Draft")
czTourMode(white, "all"); czTourMode(white, "draft")
check(s.tour.offer == offer, "switching away and back keeps the same offer")
check(logged("switched to Draft (5 decks on offer)"), "returning to Draft logs the standing offer")
czTourRedraw(white)
check(s.tour.offer ~= offer and #s.tour.offer == 5 and s.tour.redraws == 1, "Redraw deals a new offer")
check(logged("REDREW the draft (redraw #1, 5 new decks dealt)"), "redraws are logged and counted")
czPick(white, "3")
check(s.selected and s.selected.id == s.tour.offer[3].id, "pick one from the offer")

-- Random: one pool deck, selected; Reroll allowed and logged.
czTourMode(white, "random")
check(s.tour.random and inPool[s.tour.random.id] and s.selected == s.tour.random, "Random rolls and selects a pool deck")
check(#s.list == 1 and values["cz_count_White"] == "Random deck", "Random shows just that deck")
check(logged("switched to Random (rolled a deck)"), "the roll is logged, not the deck")
check(attrs["cz_tredraw_White"].text:find("Reroll", 1, true), "Reroll shown in Random")
czTourRedraw(white)
check(s.tour.rerolls == 1 and logged("REROLLED (reroll #1)"), "rerolls are logged and counted")

-- Loading is logged, success and refusal.
local rolled = s.tour.random
spawned = {}
czLoad(white)
check(logged("pressed Load into my seat"), "the load is logged")
check(logged("LOADED a deck (sleeves"), "the result is logged")
-- Hidden information: no log line or broadcast names any pool deck or commander.
for _, d in ipairs(CZ.index.decks) do
  if inPool[d.id] then
    for _, l in ipairs(logs) do
      check(not l:find(d.name, 1, true) and not l:find(d.commander, 1, true), "log never reveals " .. d.name)
    end
  end
end
for _, b in ipairs(broadcasts) do check(not b:find(rolled.name, 1, true), "broadcasts never reveal the deck") end
check(#spawned >= 2, "and the deck spawns: nothing is restricted")
czOpen(white)
check(logged("opened the browser"), "opening is logged")
inZone = {{type = "Deck"}}
czLoad(white)
check(logged("load refused: library zone not empty"), "a refused load is logged")
inZone = {}
czRefresh(white)
check(logged("refreshed the deck list"), "refresh is logged")
-- Another player can pick the same deck: no restrictions, and their log is their own.
local red = {color = "Red", steam_name = "RedName"}
czOpen(red); czTournament(red); czTourMode(red, "all")
check(logged("RedName (Red): entered tournament mode"), "each player's log names them")
czTournament(red)
check(logged("RedName (Red): left tournament mode"), "leaving is logged")
local before = #logs
czSort(red, "tier")
check(#logs == before, "after leaving, nothing more is logged")
check(attrs["cz_filters_Red"].active == "True", "filters come back")
czTournament(white)

-- A library zone that already holds a deck is left alone.
spawned, inZone = {}, {{type = "Deck"}}
czOpen(white); czLoad(white)
check(#spawned == 0, "no spawn onto an existing deck")
check(values["cz_status_White"]:find("not empty"), "and the player is told why")

print(string.format("%d checks, %d failed", checks, failures))
os.exit(failures == 0 and 0 or 1)
