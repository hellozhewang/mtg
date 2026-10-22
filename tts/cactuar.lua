--[[ ======================================================================
  Cactuar deck browser — appended to the table's Global script by
  scripts/build_tts_table.py (source: github.com/hellozhewang/mtg, tts/).

  Each seated player gets their own browser panel (tts/cactuar.xml, one copy
  per seat colour), opened by clicking a Cactuar tile on the table
  (tts/cactuar_tile.lua). It lists the decks published at CZ.base, sorts and
  filters them, and loads the chosen one into the clicking player's seat: the
  library face down and shuffled in their library zone, the commander(s) on
  their Commander Zone(s), the tokens beside them.

  Tournament mode (per player, the Tournament button) shows only the curated
  pool (decks.json "tournament", from tts/tournament.json) as All pick, Draft
  (5 offered, pick one) or Random, and logs everything that player does to
  chat. It restricts nothing: redraws and rerolls are allowed, and logged.

  Hidden information: nothing announced to the table names a deck, commander
  or search. The log says what a player did ("selected a deck", "REROLLED"),
  never which deck; the commander(s) and tokens spawn face down. A player's
  own panel (visible only to them) still shows their deck.

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
  sleeveCells = 8,     -- the Sleeves grid's page size; matches SLEEVE_CELLS in build_tts_table.py
  index = nil,        -- decks.json, once fetched
  indexAt = 0,        -- os.time() it arrived
  staleAfter = 120,   -- seconds: opening the browser after this re-fetches it
  fetching = false,
  state = {},         -- per seat colour: sort, filters, search, page, selection
  busy = {},          -- per seat colour: a deck is being loaded
  draftSize = 5,      -- decks offered in a tournament Draft
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

-- Who sits in a seat now, so a seat's browser starts fresh for a new player.
local function czSeatPlayer(color)
  local id = nil
  pcall(function() id = Player[color].steam_id end)
  return id
end

local function czState(color)
  local s = CZ.state[color]
  local who = czSeatPlayer(color)
  -- A different player took the seat: don't hand them the last player's search,
  -- selection, status or tournament.
  if s and who and s.player and s.player ~= who then s = nil end
  if not s then
    s = {sort = "newest", filter = {}, query = "", page = 1, selected = nil, list = {}, player = who}
    CZ.state[color] = s
  end
  s.player = s.player or who
  return s
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
-- ---------- sleeves ----------

-- decks.json lists them: Magic's standard back first, then the repo's tts/sleeves/.
local function czSleeves()
  return (CZ.index and CZ.index.sleeves) or {}
end

-- The player's chosen sleeves, or nil for the standard back.
local function czSleeve(s)
  for _, b in ipairs(czSleeves()) do
    if b.id == s.sleeve and b.id ~= "standard" then return b end
  end
  return nil
end

local function czSleeveLabel(s)
  local b = czSleeve(s)
  return b and b.label or "Standard"
end

-- Thumbnails. TTS's UI shows pictures only as named custom assets, so each sleeve's
-- thumbnail is registered as "czsl_<id>". setCustomAssets REPLACES the whole list, so
-- the base table's own assets are kept, and it only runs when the list changed: a
-- change makes TTS reload the UI, after which the open panels are drawn again.
local function czThumbAsset(b)
  local url = b.thumb_url or (b.thumb and (CZ.base .. b.thumb))
  return url and {name = "czsl_" .. b.id, url = url} or nil
end

local czRenderSleeves = nil   -- assigned after czRenderMenu

local function czRedrawOpen()
  for _, c in ipairs(CZ.seats) do
    local s = CZ.state[c]
    if s and s.open and s.player == czSeatPlayer(c) then
      UI.setAttribute("cz_panel_" .. c, "active", "True")
      UI.setAttribute("cz_search_" .. c, "text", s.query)
      s.guideDrawn = nil
      s.guidePainted = nil
      czRender(c)
      if czState(c).menu == "sleeve" then czRenderSleeves(c) end
    else
      UI.setAttribute("cz_panel_" .. c, "active", "False")
    end
  end
  if czsRedrawOpen then czsRedrawOpen() end
end

-- Registering named images rebuilds shared UI. Restore current private sessions
-- after it finishes, checking the live open flag so closed windows stay closed.
function czSetAssets(assets)
  CZ.imageGeneration = (CZ.imageGeneration or 0) + 1
  UI.setCustomAssets(assets)
  Wait.condition(czRedrawOpen, function() return not UI.loading end, 30, czRedrawOpen)
end

-- Guide rows replace only their own layout. Install XML and assets atomically:
-- separate reloads can restore stale XML or leave named WebP sprites white.
function czGuideXml(xml)
  CZ.imageGeneration = (CZ.imageGeneration or 0) + 1
  CZ.guideRebuilding = true
  UI.setXml(xml, UI.getCustomAssets())
  local function ready()
    CZ.guideRebuilding = false
    czRedrawOpen()
  end
  Wait.condition(ready, function() return not UI.loading end, 30, ready)
end

local function czRegisterThumbs()
  local ours, sig = {}, ""
  for _, b in ipairs(czSleeves()) do
    local a = czThumbAsset(b)
    if a then ours[#ours + 1] = a; sig = sig .. a.name .. "=" .. a.url .. ";" end
  end
  if sig == "" or sig == CZ.thumbSig then return end
  local ok = pcall(function()
    local merged = {}
    for _, a in ipairs(UI.getCustomAssets() or {}) do
      if type(a.name) ~= "string" or a.name:sub(1, 5) ~= "czsl_" then merged[#merged + 1] = a end
    end
    for _, a in ipairs(ours) do merged[#merged + 1] = a end
    CZ.thumbSig = sig
    czSetAssets(merged)
  end)
  if not ok then return end
  CZ.thumbSig = sig
end

-- Every card's BackURL becomes the chosen back. Like czImageJSON, this edits the
-- string values only: decoding and re-encoding would break CustomDeck.
local function czSleeveJSON(text, sleeve)
  if not sleeve then return text end
  local url = sleeve.url or (CZ.base .. sleeve.file)
  return (text:gsub('("BackURL"%s*:%s*")[^"]*"', function(prefix) return prefix .. url .. '"' end))
end

-- ---------- tournament mode ----------

local CZ_TOUR_MODES = {"all", "draft", "random"}
local CZ_TOUR_LABEL = {all = "All pick", draft = "Draft", random = "Random"}

-- The curated pool, in the order tts/tournament.json lists it.
local function czPool()
  local byId, out = {}, {}
  for _, d in ipairs((CZ.index and CZ.index.decks) or {}) do byId[d.id] = d end
  for _, id in ipairs((CZ.index and CZ.index.tournament) or {}) do
    if byId[id] then out[#out + 1] = byId[id] end
  end
  return out
end

local function czPlayerName(color)
  local name = nil
  pcall(function() name = Player[color].steam_name end)
  return name or color
end

-- Everything a player does in Tournament mode goes to chat, timestamped and in
-- their seat colour, so the table can see every pick, redraw and reroll.
local function czLog(color, text)
  if not czState(color).tour then return end
  local ok, clock = pcall(os.date, "%H:%M:%S")
  local rgb = {1, 1, 1}
  pcall(function() rgb = Color.fromString(color) end)
  printToAll(string.format("[Tournament %s] %s (%s): %s", ok and clock or "", czPlayerName(color), color, text), rgb)
end

-- n different decks from the pool, at random.
local function czDeal(n)
  local pool = czPool()
  for i = #pool, 2, -1 do
    local j = math.random(i)
    pool[i], pool[j] = pool[j], pool[i]
  end
  local out = {}
  for i = 1, math.min(n, #pool) do out[i] = pool[i] end
  return out
end

-- What a player in Tournament mode chooses from: the pool, their draft offer, or
-- their random deck.
local function czTourList(s)
  if s.tour.mode == "draft" then return s.tour.offer or {} end
  if s.tour.mode == "random" then return s.tour.random and {s.tour.random} or {} end
  return czPool()
end

local function czShort(text, limit)
  local out = text:match("^" .. string.rep("[\1-\127\194-\244][\128-\191]*", limit))
  return out and #out < #text and (out .. "…") or text
end

function czRender(color)
  local s = czState(color)
  if not CZ.index then return end
  local list = {}
  if s.tour then
    -- Filters are hidden in Tournament mode; search and sort apply to All pick.
    local all = s.tour.mode == "all"
    local match = {filter = {}, query = all and s.query or ""}
    for _, d in ipairs(czTourList(s)) do
      if czMatches(d, match) then list[#list + 1] = d end
    end
    if all then table.sort(list, czCompare(s.sort)) end
  else
    for _, d in ipairs(CZ.index.decks) do
      if czMatches(d, s) then list[#list + 1] = d end
    end
    table.sort(list, czCompare(s.sort))
  end
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
  if s.tour then
    local pool = #czPool()
    czText("cz_count_" .. color, s.tour.mode == "draft" and ("Draft: pick 1 of " .. #list)
      or s.tour.mode == "random" and "Random deck"
      or (#list == pool and (pool .. " tournament decks") or (#list .. " of " .. pool .. " tournament decks")))
  else
    czText("cz_count_" .. color, #list == #CZ.index.decks and (#list .. " decks")
      or (#list .. " of " .. #CZ.index.decks .. " decks"))
  end
  local tour = s.tour
  czButton("cz_tour_" .. color, tour and "Leave tournament" or "Tournament")
  UI.setAttribute("cz_tour_" .. color, "colors", tour and CZ_ACTIVE or CZ_NORMAL)
  czEnabled("cz_tour_" .. color, tour ~= nil or #czPool() > 0)
  UI.setAttribute("cz_filters_" .. color, "active", tour and "False" or "True")
  UI.setAttribute("cz_tourbar_" .. color, "active", tour and "True" or "False")
  if tour then
    for _, m in ipairs(CZ_TOUR_MODES) do
      local id = "cz_tmode_" .. m .. "_" .. color
      czButton(id, CZ_TOUR_LABEL[m])
      UI.setAttribute(id, "colors", tour.mode == m and CZ_ACTIVE or CZ_NORMAL)
    end
    UI.setAttribute("cz_tredraw_" .. color, "active", tour.mode ~= "all" and "True" or "False")
    czButton("cz_tredraw_" .. color, tour.mode == "draft" and "Redraw 5" or "Reroll")
  end
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
  czButton("cz_sleeve_" .. color, "Sleeves: " .. czSleeveLabel(czState(color)) .. " ▾")
  czEnabled("cz_sleeve_" .. color, #czSleeves() > 1)
  czEnabled("cz_load_" .. color, d ~= nil and not CZ.busy[color])
  czButton("cz_load_" .. color, CZ.busy[color] and "Loading…" or d and "Load into my seat" or "Select a deck")
  if czpRender then czpRender(color, s, d) end
end

-- A menu's choices in order: a filter's All and its values, or the sleeves.
local function czMenuChoices(color, key)
  local s, out = czState(color), {}
  if key == "sleeve" then
    for _, b in ipairs(czSleeves()) do
      out[#out + 1] = {value = b.id, label = b.label, selected = (czSleeve(s) and czSleeve(s).id or "standard") == b.id}
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
  local positions = {bracket = 16, tier = 230, theme = 444, owner = 620, sleeve = 620}
  UI.setAttribute("cz_menu_" .. color, "offsetXY", positions[s.menu] .. " -146")
  UI.setAttribute("cz_menu_" .. color, "height", tostring(53 + visible * 33 + (pages > 1 and 31 or 0)))
  UI.setAttribute("cz_menu_" .. color, "active", "True")
  UI.setAttribute("cz_scrim_" .. color, "active", "True")
  czText("cz_menu_title_" .. color, "Choose " .. (s.menu == "sleeve" and "sleeves" or string.lower(CZ_FILTER_LABEL[s.menu])))
  UI.setAttribute("cz_menu_pager_" .. color, "active", pages > 1 and "True" or "False")
  czText("cz_menu_page_" .. color, s.menuPage .. " / " .. pages)
  czEnabled("cz_menu_prev_" .. color, s.menuPage > 1)
  czEnabled("cz_menu_next_" .. color, s.menuPage < pages)
  czButton("cz_menu_prev_" .. color, "‹")
  czButton("cz_menu_next_" .. color, "›")
end

-- The Sleeves grid: CZ.sleeveCells thumbnails a page, the chosen one ticked. A sleeve
-- without a thumbnail (or before its asset has loaded) shows its name alone.
czRenderSleeves = function(color)
  local s = czState(color)
  if s.menu ~= "sleeve" then return end
  local choices = czMenuChoices(color, "sleeve")
  local sleeves = czSleeves()
  local count, size = #choices, CZ.sleeveCells
  local pages = math.max(1, math.ceil(count / size))
  s.menuPage = math.max(1, math.min(s.menuPage or 1, pages))
  for i = 1, size do
    local n = (s.menuPage - 1) * size + i
    local id = "cz_sl_" .. i .. "_" .. color
    UI.setAttribute(id, "active", n <= count and "True" or "False")
    if n <= count then
      local choice, b = choices[n], sleeves[n]
      local asset = CZ.thumbSig and b and czThumbAsset(b)
      UI.setAttribute("cz_sl_img_" .. i .. "_" .. color, "image", asset and asset.name or "")
      UI.setAttribute("cz_sl_img_" .. i .. "_" .. color, "color", asset and "#FFFFFF" or "#FFFFFF00")
      czText("cz_sl_name_" .. i .. "_" .. color, (choice.selected and "✓ " or "") .. choice.label)
      UI.setAttribute(id, "colors", choice.selected and CZ_ACTIVE or "#202F42|#344D66|#275B4B|#182331")
    end
  end
  UI.setAttribute("cz_sleeves_" .. color, "active", "True")
  UI.setAttribute("cz_scrim_" .. color, "active", "True")
  UI.setAttribute("cz_sleeves_pager_" .. color, "active", pages > 1 and "True" or "False")
  czText("cz_sleeves_page_" .. color, s.menuPage .. " / " .. pages)
  czEnabled("cz_sleeves_prev_" .. color, s.menuPage > 1)
  czEnabled("cz_sleeves_next_" .. color, s.menuPage < pages)
  czButton("cz_sleeves_prev_" .. color, "‹")
  czButton("cz_sleeves_next_" .. color, "›")
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
    CZ.index, CZ.indexAt = index, os.time()
    czRegisterThumbs()
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
  if czsClose then czsClose(player) end
  czDismiss(player)
  local id = "cz_panel_" .. color
  local s = czState(color)
  if UI.getAttribute(id, "active") == "True" then
    s.open = false
    UI.setAttribute(id, "active", "False")
    czLog(color, "closed the browser")
    return
  end
  UI.setAttribute(id, "active", "True")
  s.open = true
  if s.query == "" then UI.setAttribute("cz_search_" .. color, "text", "") end
  if s.selected == nil then czStatus(color, "") end
  czLog(color, "opened the browser")
  if CZ.index then
    czRender(color)
    -- New decks and sleever's sleeves appear without pressing Refresh: an old list
    -- shows at once and is replaced when the fresh one arrives.
    if os.time() - (CZ.indexAt or 0) > CZ.staleAfter then czFetchIndex() end
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
  czHideBrowser(player.color)
  czLog(player.color, "closed the browser")
end

function czHideBrowser(color)
  if CZ.state[color] then CZ.state[color].open = false end
  UI.setAttribute("cz_panel_" .. color, "active", "False")
end

function czRefresh(player)
  czDismiss(player)
  if czpRefresh then czpRefresh() end
  czLog(player.color, "refreshed the deck list")
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
  -- Typing calls this per keystroke: log the search once it settles.
  if s.tour then
    local color = player.color
    s.searchSeq = (s.searchSeq or 0) + 1
    local seq = s.searchSeq
    local function settle()
      if s.searchSeq ~= seq or s.loggedQuery == s.query then return end
      s.loggedQuery = s.query
      czLog(color, s.query == "" and "cleared the search" or "searched the list")
    end
    if Wait then Wait.time(settle, 1.5) else settle() end
  end
end

function czSort(player, key)
  if not CZ_SORT_LABEL[key] then return end
  czDismiss(player)
  local s = czState(player.color)
  s.sort = key
  s.page = 1
  czLog(player.color, "sorted by " .. CZ_SORT_LABEL[key])
  czRender(player.color)
end

function czDismiss(player)
  czState(player.color).menu = nil
  UI.setAttribute("cz_menu_" .. player.color, "active", "False")
  UI.setAttribute("cz_sleeves_" .. player.color, "active", "False")
  UI.setAttribute("cz_scrim_" .. player.color, "active", "False")
end

function czFilter(player, key)
  if not CZ.index or not (CZ_FILTER_LABEL[key] or key == "sleeve") then return end
  if key == "sleeve" and #czSleeves() < 2 then return end     -- an index from before sleeves
  local s = czState(player.color)
  if s.menu == key then czDismiss(player); return end
  s.menu, s.menuPage = key, 1
  -- Open the page containing the currently selected value.
  local size = key == "sleeve" and CZ.sleeveCells or CZ.menuRows
  for i, choice in ipairs(czMenuChoices(player.color, key)) do
    if choice.selected then s.menuPage = math.ceil(i / size) end
  end
  if key == "sleeve" then czRenderSleeves(player.color) else czRenderMenu(player.color) end
end

function czMenuPage(player, direction)
  local s = czState(player.color)
  if not s.menu then return end
  s.menuPage = (s.menuPage or 1) + (direction == "next" and 1 or -1)
  if s.menu == "sleeve" then czRenderSleeves(player.color) else czRenderMenu(player.color) end
end

-- A thumbnail in the Sleeves grid was clicked.
function czSleevePick(player, cell)
  local s = czState(player.color)
  local i = tonumber(cell)
  if s.menu ~= "sleeve" or not i or i < 1 or i > CZ.sleeveCells then return end
  local choices = czMenuChoices(player.color, "sleeve")
  local n = ((s.menuPage or 1) - 1) * CZ.sleeveCells + i
  if n > #choices then return end
  s.sleeve = choices[n].value                  -- applies to the next deck loaded
  czLog(player.color, "chose sleeves " .. choices[n].label)
  czDismiss(player)
  czStatus(player.color, "")
  czRender(player.color)
end

function czChoose(player, row)
  local s = czState(player.color)
  if not s.menu then return end
  local i = tonumber(row)
  if not i or i < 1 or i > CZ.menuRows then return end
  local choices = czMenuChoices(player.color, s.menu)
  local n = ((s.menuPage or 1) - 1) * CZ.menuRows + i
  if n > #choices then return end
  s.filter[s.menu] = choices[n].value        -- All (first choice) is nil
  s.page = 1
  czLog(player.color, "changed a filter")
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
  czLog(player.color, "reset the search")
  s.loggedQuery = ""
  czRender(player.color)
end

function czPage(player, direction)
  local s = czState(player.color)
  s.page = s.page + (direction == "next" and 1 or -1)
  czRender(player.color)
  czLog(player.color, "turned to page " .. s.page)
end

function czPick(player, row)
  local s = czState(player.color)
  czStatus(player.color, "")
  s.selected = s.list[(s.page - 1) * CZ.rows + tonumber(row)]
  if s.selected then czLog(player.color, "selected a deck") end
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
  czLog(player.color, "used Surprise me")
  czRender(player.color)
end

-- ---------- tournament handlers ----------

function czTournament(player)
  local color = player.color
  local s = czState(color)
  czDismiss(player)
  czStatus(color, "")
  if s.tour then
    czLog(color, "left tournament mode")
    s.tour = nil
  else
    if #czPool() == 0 then return end
    s.tour, s.page = {mode = "all", redraws = 0, rerolls = 0}, 1
    czLog(color, "entered tournament mode: All pick from " .. #czPool() .. " decks")
  end
  czRender(color)
end

function czTourMode(player, mode)
  local color = player.color
  local s = czState(color)
  if not s.tour or not CZ_TOUR_LABEL[mode] then return end
  czDismiss(player)
  czStatus(color, "")
  s.tour.mode, s.page = mode, 1
  local note = ""
  if mode == "draft" then
    local fresh = not s.tour.offer
    s.tour.offer = s.tour.offer or czDeal(CZ.draftSize)
    note = string.format(fresh and " (%d decks dealt)" or " (%d decks on offer)", #s.tour.offer)
  elseif mode == "random" then
    local fresh = not s.tour.random
    s.tour.random = s.tour.random or czDeal(1)[1]
    s.selected = s.tour.random
    note = s.tour.random and (fresh and " (rolled a deck)" or " (deck already rolled)") or ""
  end
  czLog(color, "switched to " .. CZ_TOUR_LABEL[mode] .. note)
  czRender(color)
end

-- Draft: deal a new offer. Random: roll a new deck. Allowed, and logged.
function czTourRedraw(player)
  local color = player.color
  local s = czState(color)
  if not s.tour then return end
  czDismiss(player)
  czStatus(color, "")
  if s.tour.mode == "draft" then
    s.tour.offer, s.tour.redraws, s.selected = czDeal(CZ.draftSize), s.tour.redraws + 1, nil
    czLog(color, "REDREW the draft (redraw #" .. s.tour.redraws .. ", " .. #s.tour.offer .. " new decks dealt)")
  elseif s.tour.mode == "random" then
    s.tour.random, s.tour.rerolls = czDeal(1)[1], s.tour.rerolls + 1
    s.selected = s.tour.random
    czLog(color, "REROLLED (reroll #" .. s.tour.rerolls .. ")")
  end
  czRender(color)
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
    czLog(player.color, "load failed: the deck file did not read correctly")
    return
  end
  local sleeve = czSleeve(czState(player.color))
  for i = 2, #lines do lines[i] = czSleeveJSON(czImageJSON(lines[i]), sleeve) end
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
    spawnObjectJSON({json = lines[2 + i], position = {p.x, p.y + 1.5, p.z}, rotation = {0, yaw, 180}})  -- face down: hidden until revealed
  end
  -- Tokens stay in the seat's column, out of the play area: the table's mulligan
  -- refuses while any card or deck is in the play area ("accidental mulligan
  -- press"). Commander slot two when it's free, else the exile spot between it
  -- and the library. Never past slot one: the Life Tracker sits there.
  if header.tokens then
    local second = spots[2] or spots[1]
    local at = second
    if (header.commanders or 0) >= 2 then
      at = {x = (second.x + zp.x) / 2, y = second.y, z = (second.z + zp.z) / 2}
    end
    spawnObjectJSON({
      json = lines[#lines],
      position = {at.x, at.y + 1.5, at.z},
      rotation = {0, yaw, 180},                                   -- face down too: tokens give a deck away
    })
  end
  broadcastToAll(string.format("%s loaded a deck.", player.steam_name or czPlayerName(player.color)), {0.6, 0.9, 0.6})
  czLog(player.color, "LOADED a deck (sleeves " .. czSleeveLabel(czState(player.color)) .. ")")
  czStatus(player.color, "Loaded " .. d.name .. (header.tokens and "." or ". It makes no tokens."), "success")
  czHideBrowser(player.color)
end

function czLoad(player)
  local color = player.color
  local d = czState(color).selected
  if not d then
    czStatus(color, "Pick a deck first.", "error")
    return
  end
  czLog(color, "pressed Load into my seat")
  local seat = data and data[color]
  local zone = seat and seat["libraryZone"]
  if not zone then
    czStatus(color, "This table has no library zone for " .. color .. ".", "error")
    return
  end
  for _, obj in ipairs(zone.getObjects()) do
    if obj.type == "Deck" or obj.type == "Card" then
      czStatus(color, "Your library zone is not empty: move that deck away first.", "error")
      czLog(color, "load refused: library zone not empty")
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
      czLog(color, "load failed: " .. tostring(req.error))
      czRender(color)
      return
    end
    czSpawn(player, d, req.text, zone)
    czRender(color)
  end)
end
