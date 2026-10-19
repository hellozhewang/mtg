--[[ ======================================================================
  Cactuar deck browser — appended to the table's Global script by
  scripts/build_tts_table.py (source: github.com/hellozhewang/mtg, tts/).

  Each seated player gets their own browser panel (tts/cactuar.xml, one copy
  per seat colour), opened by clicking a Cactuar tile on the table
  (tts/cactuar_tile.lua). It lists the decks published at CZ.base, sorts and
  filters them, and loads the chosen one into the clicking player's seat: the
  library face down and shuffled in their library zone, the commander(s) on
  their Commander Zone(s), the tokens beside them.

  Labels: always UI.setAttribute(id, "text", ...). setValue on a Button does
  nothing; on Text it stores raw rich-text markup that breaks the importer's
  getXmlTable/setXmlTable round-trip. Text attributes are XML-escaped instead.

  Everything here is prefixed `cz`/`CZ` so it cannot collide with the table's
  own script, and nothing runs until a player opens the browser: the table's
  `onload` is left exactly as it was.
====================================================================== ]]

CZ = {
  base = "@BASE_URL@",
  seats = {"White", "Red", "Yellow", "Green", "Blue", "Purple"},
  rows = 10,
  menuRows = 10,
  index = nil,        -- decks.json, once fetched
  fetching = false,
  state = {},         -- per seat colour: sort, filters, search, page, selection
  busy = {},          -- per seat colour: a deck is being loaded
}

local CZ_SORTS = {"tier", "name", "newest"}
local CZ_SORT_LABEL = {tier = "Tier", name = "Name", newest = "Newest"}
local CZ_FILTERS = {"bracket", "tier", "theme", "owner"}
local CZ_FILTER_LABEL = {bracket = "Bracket", tier = "Tier", theme = "Strategy", owner = "Owner"}
local CZ_DIM = "#C0C8D2"
local CZ_TEXT = "#E2E5EA"
local CZ_NORMAL = "#243244|#34485F|#1C2938|#1B2533"
local CZ_ACTIVE = "#1B3A33|#21483D|#163128|#1B2533"

local function czText(id, text)
  UI.setAttribute(id, "text", text)
end

-- Explicit rich-text colour also survives the importer's default Button styles.
local function czButton(id, text)
  czText(id, "<color=" .. CZ_TEXT .. ">" .. text .. "</color>")
end

local function czEnabled(id, enabled)
  UI.setAttribute(id, "interactable", enabled and "True" or "False")
end

-- ---------- state ----------

local function czIsSeat(color)
  for _, c in ipairs(CZ.seats) do
    if c == color then return true end
  end
  return false
end

local function czState(color)
  if not CZ.state[color] then
    CZ.state[color] = {sort = "newest", filter = {}, query = "", page = 1, selected = nil, list = {}}
  end
  return CZ.state[color]
end

local function czStatus(color, text, tone)
  czText("cz_status_" .. color, text or "")
  UI.setAttribute("cz_status_" .. color, "color",
    tone == "error" and "#FF9A9A" or tone == "success" and "#3D6554" or CZ_DIM)
end

-- ---------- the index ----------

local function czTierRank(id)
  for i, t in ipairs(CZ.index.tiers) do
    if t.id == id then return i end
  end
  return 99                       -- unrated: last
end

local function czTierColor(id)
  for _, t in ipairs(CZ.index.tiers) do
    if t.id == id then return t.color end
  end
  return "#cccccc"
end

local function czThemeLabel(id)
  for _, t in ipairs(CZ.index.themes) do
    if t.id == id then return t.label end
  end
  return id
end

-- Every value a filter can take, in display order; nil means "All".
local function czFilterValues(key)
  local values, seen = {}, {}
  if key == "tier" then
    for _, t in ipairs(CZ.index.tiers) do values[#values + 1] = t.id end
    return values
  elseif key == "theme" then
    for _, t in ipairs(CZ.index.themes) do values[#values + 1] = t.id end
    return values
  end
  for _, d in ipairs(CZ.index.decks) do
    local v = d[key]
    if v and v ~= "" and not seen[v] then
      seen[v] = true
      values[#values + 1] = v
    end
  end
  table.sort(values, function(a, b) return string.lower(a) < string.lower(b) end)
  return values
end

local function czFilterLabel(key, value)
  if value == nil then return CZ_FILTER_LABEL[key] .. ": All" end
  if key == "theme" then return czThemeLabel(value) end
  if key == "bracket" then
    for _, d in ipairs(CZ.index.decks) do
      if d.bracket == value then return d.bracketLabel end
    end
  end
  if key == "tier" then return value .. " tier" end
  return value
end

local function czHaystack(d)
  local parts = {d.name, d.commander, d.owner, d.bracketLabel, d.tier ~= "" and (d.tier .. "-tier") or "unrated"}
  for _, t in ipairs(d.themes or {}) do parts[#parts + 1] = czThemeLabel(t) end
  return string.lower(table.concat(parts, " "))
end

local function czMatches(d, s)
  for key, value in pairs(s.filter) do
    if key == "theme" then
      local hit = false
      for _, t in ipairs(d.themes or {}) do
        if t == value then hit = true end
      end
      if not hit then return false end
    elseif d[key] ~= value then
      return false
    end
  end
  if s.query ~= "" then
    local hay = czHaystack(d)
    for term in string.gmatch(string.lower(s.query), "%S+") do
      if not string.find(hay, term, 1, true) then return false end
    end
  end
  return true
end

local function czCompare(sort)
  local function byName(a, b)
    if string.lower(a.name) ~= string.lower(b.name) then
      return string.lower(a.name) < string.lower(b.name)
    end
    return a.owner < b.owner
  end
  if sort == "name" then return byName end
  if sort == "newest" then
    return function(a, b)
      if a.added ~= b.added then return a.added > b.added end
      return byName(a, b)
    end
  end
  return function(a, b)                               -- tier: strongest first
    if czTierRank(a.tier) ~= czTierRank(b.tier) then return czTierRank(a.tier) < czTierRank(b.tier) end
    return byName(a, b)
  end
end

-- ---------- drawing one player's panel ----------

local function czDate(ts)
  if not ts or ts == 0 then return nil end
  local ok, text = pcall(os.date, "%Y-%m-%d", ts)
  return ok and text or nil
end

local function czDetail(d)
  if not d then return "<size=20><b>Find your next deck</b></size>\n\nSelect a deck from the list to see its commander, strategy and stats.\n\n<color=" .. CZ_DIM .. ">Search as you type, choose a filter, or try Surprise me.</color>" end
  local themes = {}
  for _, t in ipairs(d.themes or {}) do themes[#themes + 1] = czThemeLabel(t) end
  local tier = d.tier ~= "" and string.format("<color=%s><b>%s tier</b></color>", czTierColor(d.tier), d.tier) or "Unrated"
  return string.format(
    "<size=18><b>%s</b></size>\n<color=%s>%s</color>\n\n%s · %s\n<color=%s>by %s</color>\n\n<size=11><color=%s>STRATEGY</color></size>\n%s",
    d.name, CZ_DIM, d.commander, tier, d.bracketLabel, CZ_DIM, d.owner, CZ_DIM,
    #themes > 0 and table.concat(themes, "\n") or "Uncategorised")
end

-- Unity's single-line Text clips overflow. Keep the owner visible even with long
-- partner names; the details panel always contains the complete commander text.
-- ---------- card backs ----------

-- decks.json lists them: Magic's standard back first, then the repo's tts/backs/.
local function czBacks()
  return (CZ.index and CZ.index.backs) or {}
end

-- The player's chosen back, or nil for the standard one.
local function czBack(s)
  for _, b in ipairs(czBacks()) do
    if b.id == s.back and b.id ~= "standard" then return b end
  end
  return nil
end

local function czBackLabel(s)
  local b = czBack(s)
  return b and b.label or "Standard"
end

-- Every card's BackURL becomes the chosen back. Like czImageJSON, this edits the
-- string values only: decoding and re-encoding would break CustomDeck.
local function czBackJSON(text, back)
  if not back then return text end
  local url = back.url or (CZ.base .. back.file)
  return (text:gsub('("BackURL"%s*:%s*")[^"]*"', function(prefix) return prefix .. url .. '"' end))
end

local function czShort(text, limit)
  local out = text:match("^" .. string.rep("[\1-\127\194-\244][\128-\191]*", limit))
  return out and #out < #text and (out .. "…") or text
end

function czRender(color)
  local s = czState(color)
  if not CZ.index then return end
  local list = {}
  for _, d in ipairs(CZ.index.decks) do
    if czMatches(d, s) then list[#list + 1] = d end
  end
  table.sort(list, czCompare(s.sort))
  s.list = list
  if s.selected then
    local selected = nil
    for _, d in ipairs(list) do if d.id == s.selected.id then selected = d end end
    s.selected = selected     -- don't offer to load a stale or filtered-out deck
  end
  local pages = math.max(1, math.ceil(#list / CZ.rows))
  if s.page > pages then s.page = pages end
  if s.page < 1 then s.page = 1 end
  for i = 1, CZ.rows do
    local d = list[(s.page - 1) * CZ.rows + i]
    local id = "cz_row_" .. i .. "_" .. color
    if d then
      local selected = s.selected and s.selected.id == d.id
      czText("cz_row_name_" .. i .. "_" .. color, czShort(d.name, 51))
      czText("cz_row_sub_" .. i .. "_" .. color, czShort(d.commander, 52) .. " · " .. d.owner)
      czText("cz_row_tier_" .. i .. "_" .. color, d.tier ~= "" and d.tier or "?")
      UI.setAttribute("cz_row_tier_" .. i .. "_" .. color, "color", czTierColor(d.tier))
      UI.setAttribute(id, "colors", selected and CZ_ACTIVE or "#1C2939|#2D4157|#244E46|#182331")
      UI.setAttribute(id, "active", "True")
    else
      UI.setAttribute(id, "active", "False")
    end
  end
  czText("cz_page_" .. color, string.format("Page %d / %d", s.page, pages))
  czText("cz_count_" .. color, #list == #CZ.index.decks and (#list .. " decks")
    or (#list .. " of " .. #CZ.index.decks .. " decks"))
  UI.setAttribute("cz_empty_" .. color, "active", #list == 0 and "True" or "False")
  czEnabled("cz_prev_" .. color, s.page > 1)
  czEnabled("cz_next_" .. color, s.page < pages)
  czEnabled("cz_random_" .. color, #list > 0)
  czEnabled("cz_reset_" .. color, s.query ~= "" or next(s.filter) ~= nil)
  for key, label in pairs({prev = "‹", next = "›", random = "Surprise me", reset = "Reset", close = "×",
                          refresh = CZ.fetching and "Refreshing…" or "Refresh"}) do
    czButton("cz_" .. key .. "_" .. color, label)
  end
  for _, key in ipairs(CZ_SORTS) do
    local id = "cz_sort_" .. key .. "_" .. color
    UI.setAttribute(id, "colors", s.sort == key and CZ_ACTIVE or CZ_NORMAL)
    czButton(id, CZ_SORT_LABEL[key])
  end
  for _, key in ipairs(CZ_FILTERS) do
    local id = "cz_f_" .. key .. "_" .. color
    czButton(id, czFilterLabel(key, s.filter[key]) .. " ▾")
    UI.setAttribute(id, "colors", s.filter[key] and CZ_ACTIVE or CZ_NORMAL)
  end
  local d = s.selected
  czText("cz_detail_" .. color, czDetail(d))
  UI.setAttribute("cz_stats_" .. color, "active", d and "True" or "False")
  if d then
    local function stat(id, value, label)
      czText("cz_" .. id .. "_" .. color, "<size=20><b>" .. value .. "</b></size>\n<color=" .. CZ_DIM .. "><size=10>" .. label .. "</size></color>")
    end
    stat("gc", d.gc .. (d.cap and ("/" .. d.cap) or ""), "GAME CHANGERS")
    stat("mv", string.format("%.2f", d.mv), "AVG MV")
    stat("lands", d.lands, "LANDS")
  end
  local dates = {}
  if d and czDate(d.added) then dates[#dates + 1] = "Added " .. czDate(d.added) end
  if d and czDate(d.updated) then dates[#dates + 1] = "Updated " .. czDate(d.updated) end
  czText("cz_dates_" .. color, table.concat(dates, "\n"))
  czButton("cz_back_" .. color, "Card back: " .. czBackLabel(czState(color)) .. " ▾")
  czEnabled("cz_back_" .. color, #czBacks() > 1)
  czEnabled("cz_load_" .. color, d ~= nil and not CZ.busy[color])
  czButton("cz_load_" .. color, CZ.busy[color] and "Loading…" or d and "Load into my seat" or "Select a deck")
end

-- A menu's choices in order: a filter's All and its values, or the card backs.
local function czMenuChoices(color, key)
  local s, out = czState(color), {}
  if key == "back" then
    for _, b in ipairs(czBacks()) do
      out[#out + 1] = {value = b.id, label = b.label, selected = (czBack(s) and czBack(s).id or "standard") == b.id}
    end
    return out
  end
  out[1] = {value = nil, label = czFilterLabel(key, nil), selected = s.filter[key] == nil}
  for _, v in ipairs(czFilterValues(key)) do
    out[#out + 1] = {value = v, label = czFilterLabel(key, v), selected = s.filter[key] == v}
  end
  return out
end

-- A small menu of Buttons avoids rebuilding Global UI or putting ampersands in
-- Option values. It remains safe when the table's other importer round-trips it.
local function czRenderMenu(color)
  local s = czState(color)
  if not s.menu then return end
  local choices = czMenuChoices(color, s.menu)
  local count = #choices
  local pages = math.max(1, math.ceil(count / CZ.menuRows))
  s.menuPage = math.max(1, math.min(s.menuPage or 1, pages))
  local visible = math.min(CZ.menuRows, count - (s.menuPage - 1) * CZ.menuRows)
  for i = 1, CZ.menuRows do
    local n = (s.menuPage - 1) * CZ.menuRows + i
    local id = "cz_choice_" .. i .. "_" .. color
    UI.setAttribute(id, "active", n <= count and "True" or "False")
    if n <= count then
      local choice = choices[n]
      czButton(id, (choice.selected and "✓  " or "    ") .. choice.label)
      UI.setAttribute(id, "colors", choice.selected and CZ_ACTIVE or "#202F42|#344D66|#275B4B|#182331")
    end
  end
  local positions = {bracket = 16, tier = 230, theme = 444, owner = 620, back = 620}
  UI.setAttribute("cz_menu_" .. color, "offsetXY", positions[s.menu] .. " -146")
  UI.setAttribute("cz_menu_" .. color, "height", tostring(53 + visible * 33 + (pages > 1 and 31 or 0)))
  UI.setAttribute("cz_menu_" .. color, "active", "True")
  UI.setAttribute("cz_scrim_" .. color, "active", "True")
  czText("cz_menu_title_" .. color, "Choose " .. (s.menu == "back" and "a card back" or string.lower(CZ_FILTER_LABEL[s.menu])))
  UI.setAttribute("cz_menu_pager_" .. color, "active", pages > 1 and "True" or "False")
  czText("cz_menu_page_" .. color, s.menuPage .. " / " .. pages)
  czEnabled("cz_menu_prev_" .. color, s.menuPage > 1)
  czEnabled("cz_menu_next_" .. color, s.menuPage < pages)
  czButton("cz_menu_prev_" .. color, "‹")
  czButton("cz_menu_next_" .. color, "›")
end

-- ---------- fetching ----------

local function czFetchIndex(then_)
  if CZ.fetching then return end
  CZ.fetching = true
  for _, c in ipairs(CZ.seats) do
    czEnabled("cz_refresh_" .. c, false)
    czButton("cz_refresh_" .. c, "Refreshing…")
  end
  WebRequest.get(CZ.base .. "decks.json?t=" .. os.time(), function(req)
    CZ.fetching = false
    for _, c in ipairs(CZ.seats) do
      czEnabled("cz_refresh_" .. c, true)
      czButton("cz_refresh_" .. c, "Refresh")
    end
    if req.is_error then
      for _, c in ipairs(CZ.seats) do czStatus(c, "Could not reach the deck list: " .. tostring(req.error), "error") end
      return
    end
    local ok, index = pcall(JSON.decode, req.text)
    if not ok or type(index) ~= "table" or not index.decks then
      for _, c in ipairs(CZ.seats) do czStatus(c, "The deck list did not read as JSON.", "error") end
      return
    end
    CZ.index = index
    for _, c in ipairs(CZ.seats) do
      czStatus(c, "")
      czRender(c)
    end
    if then_ then then_() end
  end)
end

-- ---------- UI handlers (named in tts/cactuar.xml) ----------

function czOpen(player)
  local color = player.color
  if not czIsSeat(color) then
    broadcastToColor("Take a seat first: decks load into your own seat.", color, {1, 0.8, 0.4})
    return
  end
  czDismiss(player)
  local id = "cz_panel_" .. color
  if UI.getAttribute(id, "active") == "True" then
    UI.setAttribute(id, "active", "False")
    return
  end
  UI.setAttribute(id, "active", "True")
  if CZ.index then
    czRender(color)
  else
    czStatus(color, "Loading the deck list…")
    czFetchIndex()
  end
end

-- The Cactuar tiles call this: Global.call("czOpenFor", {color = <clicker>}).
function czOpenFor(params)
  czOpen({color = params.color})
end

function czClose(player)
  czDismiss(player)
  UI.setAttribute("cz_panel_" .. player.color, "active", "False")
end

function czRefresh(player)
  czDismiss(player)
  czStatus(player.color, "Loading the deck list…")
  czFetchIndex()
end

function czSearch(player, value)
  local s = czState(player.color)
  if s.query == (value or "") then return end
  czDismiss(player)
  czStatus(player.color, "")
  s.query = value or ""
  s.page = 1
  czRender(player.color)
end

function czSort(player, key)
  if not CZ_SORT_LABEL[key] then return end
  czDismiss(player)
  local s = czState(player.color)
  s.sort = key
  s.page = 1
  czRender(player.color)
end

function czDismiss(player)
  czState(player.color).menu = nil
  UI.setAttribute("cz_menu_" .. player.color, "active", "False")
  UI.setAttribute("cz_scrim_" .. player.color, "active", "False")
end

function czFilter(player, key)
  if not CZ.index or not (CZ_FILTER_LABEL[key] or key == "back") then return end
  if key == "back" and #czBacks() < 2 then return end     -- an index from before card backs
  local s = czState(player.color)
  if s.menu == key then czDismiss(player); return end
  s.menu, s.menuPage = key, 1
  -- Open the menu page containing the currently selected value.
  for i, choice in ipairs(czMenuChoices(player.color, key)) do
    if choice.selected then s.menuPage = math.ceil(i / CZ.menuRows) end
  end
  czRenderMenu(player.color)
end

function czMenuPage(player, direction)
  local s = czState(player.color)
  if not s.menu then return end
  s.menuPage = (s.menuPage or 1) + (direction == "next" and 1 or -1)
  czRenderMenu(player.color)
end

function czChoose(player, row)
  local s = czState(player.color)
  if not s.menu then return end
  local i = tonumber(row)
  if not i or i < 1 or i > CZ.menuRows then return end
  local choices = czMenuChoices(player.color, s.menu)
  local n = ((s.menuPage or 1) - 1) * CZ.menuRows + i
  if n > #choices then return end
  if s.menu == "back" then
    s.back = choices[n].value                -- applies to the next deck loaded
  else
    s.filter[s.menu] = choices[n].value      -- All (first choice) is nil
    s.page = 1
  end
  czDismiss(player)
  czStatus(player.color, "")
  czRender(player.color)
end

-- Step a filter to its next value; past the last one it returns to All.
function czCycle(player, key)
  if not CZ.index then return end
  local s = czState(player.color)
  local values = czFilterValues(key)
  local current, nextValue = s.filter[key], values[1]
  if current ~= nil then
    nextValue = nil
    for i, v in ipairs(values) do
      if v == current then nextValue = values[i + 1] end
    end
  end
  s.filter[key] = nextValue
  s.page = 1
  czRender(player.color)
end

function czClear(player)
  local s = czState(player.color)
  czDismiss(player)
  czStatus(player.color, "")
  s.filter, s.query, s.page = {}, "", 1
  UI.setAttribute("cz_search_" .. player.color, "text", "")
  czRender(player.color)
end

function czPage(player, direction)
  local s = czState(player.color)
  s.page = s.page + (direction == "next" and 1 or -1)
  czRender(player.color)
end

function czPick(player, row)
  local s = czState(player.color)
  czStatus(player.color, "")
  s.selected = s.list[(s.page - 1) * CZ.rows + tonumber(row)]
  czRender(player.color)
end

function czRandom(player)
  local s = czState(player.color)
  if #s.list == 0 then return end
  czStatus(player.color, "")
  s.selected = s.list[math.random(#s.list)]
  for i, d in ipairs(s.list) do
    if d.id == s.selected.id then s.page = math.ceil(i / CZ.rows) end
  end
  czRender(player.color)
end

-- ---------- loading a deck into a seat ----------

-- Older exports point straight at Scryfall, which rejects UnityPlayer requests.
-- Change only FaceURL string values, never decode/re-encode the object: doing
-- that would turn CustomDeck's numeric-keyed maps into arrays. Current exports
-- already use this image cache and pass through untouched.
local function czImageJSON(text)
  return (text:gsub('("FaceURL"%s*:%s*")https://cards%.scryfall%.io/[^/"]+/([^"]+)"',
    function(prefix, path)
      local face = path:gsub("[?#].*$", ""):gsub("%.[^./]+$", ".webp")
      return prefix .. "https://img.klrmngr.com/display/" .. face .. '"'
    end))
end

-- Pick this seat's nearest two Commander Zones, then put the first slot (toward
-- the life tracker, farther from the library) first. A partner takes slot two,
-- toward the library. The order is the same from either side of the table.
local function czCommanderSpots(zone)
  local zp = zone.getPosition()
  local found = {}
  for _, obj in ipairs(getAllObjects()) do
    if obj.getName() == "Commander Zone" then
      local p = obj.getPosition()
      local dist = (p.x - zp.x) ^ 2 + (p.z - zp.z) ^ 2
      if dist < 400 then found[#found + 1] = {pos = p, dist = dist} end
    end
  end
  table.sort(found, function(a, b) return a.dist < b.dist end)
  local spots = {}
  for i = math.min(2, #found), 1, -1 do spots[#spots + 1] = found[i].pos end
  if #spots == 0 then
    local f = zone.getTransformForward()
    for i, step in ipairs({10.5, 6.8}) do
      spots[i] = {x = zp.x + f.x * step, y = zp.y, z = zp.z + f.z * step}
    end
  end
  return spots
end

local function czSpawn(player, d, text, zone)
  local lines = {}
  for line in string.gmatch(text, "[^\n]+") do lines[#lines + 1] = line end
  local ok, header = pcall(JSON.decode, lines[1] or "")
  if not ok or type(header) ~= "table" or not lines[2] then
    czStatus(player.color, "That deck file did not read correctly.", "error")
    return
  end
  local back = czBack(czState(player.color))
  for i = 2, #lines do lines[i] = czBackJSON(czImageJSON(lines[i]), back) end
  local zp, yaw = zone.getPosition(), zone.getRotation().y + 180
  spawnObjectJSON({
    json = lines[2],
    position = {zp.x, zp.y + 1.5, zp.z},
    rotation = {0, yaw, 180},                                   -- face down
    callback_function = function(obj) obj.shuffle() end,
  })
  local spots = czCommanderSpots(zone)
  for i = 1, header.commanders or 0 do
    local p = spots[i] or spots[#spots]
    spawnObjectJSON({json = lines[2 + i], position = {p.x, p.y + 1.5, p.z}, rotation = {0, yaw, 0}})
  end
  -- Tokens go into the battlefield beside the first slot. Not beyond it along the
  -- column: the Life Tracker sits there, and its overlay hides a pile on top.
  if header.tokens then
    local r, first = zone.getTransformRight(), spots[1]
    spawnObjectJSON({
      json = lines[#lines],
      position = {first.x - r.x * 4.2, first.y + 1.5, first.z - r.z * 4.2},
      rotation = {0, yaw, 0},
    })
  end
  broadcastToAll(string.format("%s loaded %s (%s)", player.steam_name, d.name, d.commander), {0.6, 0.9, 0.6})
  czStatus(player.color, "Loaded " .. d.name .. (header.tokens and "." or ". It makes no tokens."), "success")
  UI.setAttribute("cz_panel_" .. player.color, "active", "False")
end

function czLoad(player)
  local color = player.color
  local d = czState(color).selected
  if not d then
    czStatus(color, "Pick a deck first.", "error")
    return
  end
  local seat = data and data[color]
  local zone = seat and seat["libraryZone"]
  if not zone then
    czStatus(color, "This table has no library zone for " .. color .. ".", "error")
    return
  end
  for _, obj in ipairs(zone.getObjects()) do
    if obj.type == "Deck" or obj.type == "Card" then
      czStatus(color, "Your library zone is not empty: move that deck away first.", "error")
      return
    end
  end
  if CZ.busy[color] then return end
  CZ.busy[color] = true
  czStatus(color, "Loading " .. d.name .. "…")
  czRender(color)
  WebRequest.get(CZ.base .. d.file .. "?t=" .. os.time(), function(req)
    CZ.busy[color] = nil
    if req.is_error then
      czStatus(color, "Could not load " .. d.name .. ": " .. tostring(req.error), "error")
      czRender(color)
      return
    end
    czSpawn(player, d, req.text, zone)
    czRender(color)
  end)
end
