--[[ ======================================================================
  Cactuar deck browser — appended to the table's Global script by
  scripts/build_tts_table.py (source: github.com/hellozhewang/mtg, tts/).

  Each seated player gets their own browser panel (tts/cactuar.xml, one copy
  per seat colour). It lists the decks published at CZ.base, sorts and filters
  them, and loads the chosen one into the clicking player's seat: the library
  face down and shuffled in their library zone, the commander(s) on their
  Commander Zone(s), the tokens beside them.

  Everything here is prefixed `cz`/`CZ` so it cannot collide with the table's
  own script, and nothing runs until a player opens the browser: the table's
  `onload` is left exactly as it was.
====================================================================== ]]

CZ = {
  base = "@BASE_URL@",
  seats = {"White", "Red", "Yellow", "Green", "Blue", "Purple"},
  rows = 12,
  index = nil,        -- decks.json, once fetched
  fetching = false,
  state = {},         -- per seat colour: sort, filters, search, page, selection
  busy = {},          -- per seat colour: a deck is being loaded
}

local CZ_SORTS = {"tier", "name", "newest", "owner"}
local CZ_SORT_LABEL = {tier = "Tier", name = "Name", newest = "Newest", owner = "Owner"}
local CZ_FILTERS = {"bracket", "tier", "theme", "owner"}
local CZ_FILTER_LABEL = {bracket = "Bracket", tier = "Tier", theme = "Category", owner = "Owner"}
local CZ_DIM = "#9aa3b5"

-- ---------- state ----------

local function czIsSeat(color)
  for _, c in ipairs(CZ.seats) do
    if c == color then return true end
  end
  return false
end

local function czState(color)
  if not CZ.state[color] then
    CZ.state[color] = {sort = "tier", filter = {}, query = "", page = 1, selected = nil, list = {}}
  end
  return CZ.state[color]
end

local function czStatus(color, text)
  UI.setValue("cz_status_" .. color, text or "")
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
  if sort == "owner" then
    return function(a, b)
      if a.owner ~= b.owner then return string.lower(a.owner) < string.lower(b.owner) end
      if czTierRank(a.tier) ~= czTierRank(b.tier) then return czTierRank(a.tier) < czTierRank(b.tier) end
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
  if not d then return "Pick a deck from the list." end
  local themes = {}
  for _, t in ipairs(d.themes or {}) do themes[#themes + 1] = czThemeLabel(t) end
  local tier = d.tier ~= "" and string.format("<color=%s><b>%s tier</b></color>", czTierColor(d.tier), d.tier) or "Unrated"
  local dates = {}
  if czDate(d.added) then dates[#dates + 1] = "added " .. czDate(d.added) end
  if czDate(d.updated) then dates[#dates + 1] = "updated " .. czDate(d.updated) end
  local cap = d.cap and ("/" .. d.cap) or ""
  return string.format(
    "<size=17><b>%s</b></size>\n%s\n%s · %s · by %s\n%s\nGame Changers %d%s · avg MV %.2f · %d lands%s",
    d.name, d.commander, d.bracketLabel, tier, d.owner,
    #themes > 0 and table.concat(themes, ", ") or "",
    d.gc, cap, d.mv, d.lands,
    #dates > 0 and ("\n<color=" .. CZ_DIM .. ">" .. table.concat(dates, " · ") .. "</color>") or "")
end

local function czRow(d, selected)
  local tier = d.tier ~= "" and d.tier or "?"
  local text = string.format("<color=%s><b>%-5s</b></color> <b>%s</b>  <color=%s>%s · %s</color>",
    czTierColor(d.tier), tier, d.name, CZ_DIM, d.commander, d.owner)
  return text, selected and "rgba(0.25,0.35,0.55,1)" or "rgba(0.16,0.17,0.21,1)"
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
  local pages = math.max(1, math.ceil(#list / CZ.rows))
  if s.page > pages then s.page = pages end
  if s.page < 1 then s.page = 1 end
  for i = 1, CZ.rows do
    local d = list[(s.page - 1) * CZ.rows + i]
    local id = "cz_row_" .. i .. "_" .. color
    if d then
      local text, bg = czRow(d, s.selected and s.selected.id == d.id)
      UI.setValue(id, text)
      UI.setAttribute(id, "color", bg)
      UI.setAttribute(id, "active", "True")
    else
      UI.setAttribute(id, "active", "False")
    end
  end
  UI.setValue("cz_page_" .. color, string.format("Page %d / %d · %d deck%s", s.page, pages, #list, #list == 1 and "" or "s"))
  for _, key in ipairs(CZ_SORTS) do
    UI.setAttribute("cz_sort_" .. key .. "_" .. color, "color",
      s.sort == key and "rgba(0.25,0.45,0.30,1)" or "rgba(0.22,0.23,0.28,1)")
  end
  for _, key in ipairs(CZ_FILTERS) do
    UI.setValue("cz_f_" .. key .. "_" .. color, czFilterLabel(key, s.filter[key]))
  end
  UI.setValue("cz_detail_" .. color, czDetail(s.selected))
end

-- ---------- fetching ----------

local function czFetchIndex(then_)
  if CZ.fetching then return end
  CZ.fetching = true
  WebRequest.get(CZ.base .. "decks.json?t=" .. os.time(), function(req)
    CZ.fetching = false
    if req.is_error then
      for _, c in ipairs(CZ.seats) do czStatus(c, "Could not reach the deck list: " .. tostring(req.error)) end
      return
    end
    local ok, index = pcall(JSON.decode, req.text)
    if not ok or type(index) ~= "table" or not index.decks then
      for _, c in ipairs(CZ.seats) do czStatus(c, "The deck list did not read as JSON.") end
      return
    end
    CZ.index = index
    for _, c in ipairs(CZ.seats) do
      czStatus(c, #index.decks .. " decks")
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

function czClose(player)
  UI.setAttribute("cz_panel_" .. player.color, "active", "False")
end

function czRefresh(player)
  czStatus(player.color, "Loading the deck list…")
  czFetchIndex()
end

function czSearch(player, value)
  local s = czState(player.color)
  s.query = value or ""
  s.page = 1
  czRender(player.color)
end

function czSort(player, key)
  local s = czState(player.color)
  s.sort = key
  s.page = 1
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
  s.selected = s.list[(s.page - 1) * CZ.rows + tonumber(row)]
  czRender(player.color)
end

function czRandom(player)
  local s = czState(player.color)
  if #s.list == 0 then return end
  s.selected = s.list[math.random(#s.list)]
  for i, d in ipairs(s.list) do
    if d.id == s.selected.id then s.page = math.ceil(i / CZ.rows) end
  end
  czRender(player.color)
end

-- ---------- loading a deck into a seat ----------

-- This seat's Commander Zones, nearest first: the table has two per seat, so a
-- partner pair gets one each. Falls back to points past the exile spot.
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
  for i = 1, math.min(2, #found) do spots[i] = found[i].pos end
  if #spots == 0 then
    local f = zone.getTransformForward()
    for i, step in ipairs({6.8, 10.5}) do
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
    czStatus(player.color, "That deck file did not read correctly.")
    return
  end
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
  if header.tokens then
    local f, last = zone.getTransformForward(), spots[#spots]
    spawnObjectJSON({
      json = lines[#lines],
      position = {last.x + f.x * 3.8, last.y + 1.5, last.z + f.z * 3.8},
      rotation = {0, yaw, 0},
    })
  end
  broadcastToAll(string.format("%s loaded %s (%s)", player.steam_name, d.name, d.commander), {0.6, 0.9, 0.6})
  czStatus(player.color, "Loaded " .. d.name .. ".")
  UI.setAttribute("cz_panel_" .. player.color, "active", "False")
end

function czLoad(player)
  local color = player.color
  local d = czState(color).selected
  if not d then
    czStatus(color, "Pick a deck first.")
    return
  end
  local seat = data and data[color]
  local zone = seat and seat["libraryZone"]
  if not zone then
    czStatus(color, "This table has no library zone for " .. color .. ".")
    return
  end
  for _, obj in ipairs(zone.getObjects()) do
    if obj.type == "Deck" or obj.type == "Card" then
      czStatus(color, "Your library zone is not empty: move that deck away first.")
      return
    end
  end
  if CZ.busy[color] then return end
  CZ.busy[color] = true
  czStatus(color, "Loading " .. d.name .. "…")
  WebRequest.get(CZ.base .. d.file .. "?t=" .. os.time(), function(req)
    CZ.busy[color] = nil
    if req.is_error then
      czStatus(color, "Could not load " .. d.name .. ": " .. tostring(req.error))
      return
    end
    czSpawn(player, d, req.text, zone)
  end)
end
