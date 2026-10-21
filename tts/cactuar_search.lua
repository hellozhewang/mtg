-- Alphabetical, private search of a real deck. Sorting happens only in Lua's
-- copied metadata, never in the container. No deck indexes reach the UI.
-- Native Search has no scripted sort option: api.tabletopsimulator.com/behavior/container/
local czsPrevious = CZS
if czsPrevious and czsPrevious.ticker then Wait.stop(czsPrevious.ticker) end
CZS = {state = {}, attached = czsPrevious and czsPrevious.attached or {}, cells = 12}

local function czsText(id, text) UI.setAttribute(id, "text", text or "") end
local function czsActive(id, active) UI.setAttribute(id, "active", active and "True" or "False") end
local function czsEnabled(id, enabled) UI.setAttribute(id, "interactable", enabled and "True" or "False") end
local function czsOwner(color)
  local p = Player[color]
  return p and tostring(p.steam_id or p.steam_name or color) or nil
end
local function czsSeat(color)
  for _, c in ipairs(CZ.seats) do if c == color then return true end end
  return false
end
local function czsSession(player, id)
  if not player or not czsSeat(player.color) then return nil end
  if id and id:match("_([%a]+)$") ~= player.color then return nil end
  local s = CZS.state[player.color]
  if s and s.owner == czsOwner(player.color) then return s end
  return nil
end
local function czsEscape(text)
  -- Names are plain text even if an imported card has a rich-text-looking name.
  return (text:gsub("&", "&amp;"):gsub("<", "&lt;"):gsub(">", "&gt;"))
end
local function czsName(text)
  local first = (text or ""):match("^[^\r\n]*") or ""
  first = first:gsub("%[%x%x%x%x%x%x%]", ""):gsub("%[%-%]", "")
  return first:match("%S") and first or "Unnamed card"
end
local function czsKey(text)
  local accents = { ["À"]="a", ["Á"]="a", ["Â"]="a", ["Ã"]="a", ["Ä"]="a", ["Å"]="a",
    ["à"]="a", ["á"]="a", ["â"]="a", ["ã"]="a", ["ä"]="a", ["å"]="a", ["Æ"]="ae", ["æ"]="ae",
    ["Ç"]="c", ["ç"]="c", ["È"]="e", ["É"]="e", ["Ê"]="e", ["Ë"]="e",
    ["è"]="e", ["é"]="e", ["ê"]="e", ["ë"]="e", ["Ì"]="i", ["Í"]="i", ["Î"]="i", ["Ï"]="i",
    ["ì"]="i", ["í"]="i", ["î"]="i", ["ï"]="i", ["Ñ"]="n", ["ñ"]="n",
    ["Ò"]="o", ["Ó"]="o", ["Ô"]="o", ["Õ"]="o", ["Ö"]="o", ["Ø"]="o",
    ["ò"]="o", ["ó"]="o", ["ô"]="o", ["õ"]="o", ["ö"]="o", ["ø"]="o", ["Œ"]="oe", ["œ"]="oe",
    ["Ù"]="u", ["Ú"]="u", ["Û"]="u", ["Ü"]="u", ["ù"]="u", ["ú"]="u", ["û"]="u", ["ü"]="u" }
  return string.lower((text:gsub("[\194-\244][\128-\191]*", accents)))
end
local function czsDeck(s)
  local obj = getObjectFromGUID(s.deck)
  return obj and (obj.type == "Deck" or obj.tag == "Deck") and obj or nil
end

local function czsImage(url)
  if type(url) ~= "string" then return nil end
  local path = url:match("^https://cards%.scryfall%.io/[^/]+/(.+)$")
  if path then
    path = path:gsub("[?#].*$", ""):gsub("%.[^./]+$", ".webp")
    return "https://img.klrmngr.com/display/" .. path
  end
  return url:match("^https?://") and url or nil
end
local function czsPictures(deck)
  local ok, data = pcall(function() return deck.getData() end)
  if not ok or type(data) ~= "table" then return {} end
  local pictures = {}
  for _, card in ipairs(data.ContainedObjects or {}) do
    local key = math.floor((card.CardID or 0) / 100)
    local own, shared = card.CustomDeck or {}, data.CustomDeck or {}
    local sheet = own[tostring(key)] or own[key] or shared[tostring(key)] or shared[key]
    -- Our catalog and rikrassen's importer use single-card textures. For an
    -- atlas keep the named entry usable, rather than showing a whole sheet.
    if card.GUID and sheet and (sheet.NumWidth or 1) == 1 and (sheet.NumHeight or 1) == 1 then
      pictures[card.GUID] = czsImage(sheet.FaceURL)
    end
  end
  return pictures
end

local function czsRender(color)
  local s = CZS.state[color]
  if not s then return end
  local query, filtered = czsKey(s.query), {}
  for _, card in ipairs(s.cards) do
    if card.key:find(query, 1, true) then filtered[#filtered + 1] = card end
  end
  local pages = math.max(1, math.ceil(#filtered / CZS.cells))
  s.page = math.max(1, math.min(s.page, pages))
  s.shown = {}
  local selected = nil
  for _, card in ipairs(s.cards) do if card.guid == s.selected then selected = card end end
  if not selected then s.selected = nil; czsActive("czs_preview_" .. color, false) end
  for i = 1, CZS.cells do
    local card = filtered[(s.page - 1) * CZS.cells + i]
    local suffix = i .. "_" .. color
    czsActive("czs_card_" .. suffix, card ~= nil)
    if card then
      s.shown[i] = card.guid
      -- Bind the GUID into the client-side callback. A late click on an older
      -- page must never be reinterpreted as the new occupant of that slot.
      UI.setAttribute("czs_card_" .. suffix, "onClick", "czsPick(" .. card.guid .. ")")
      czsText("czs_name_" .. suffix, czsEscape(card.name))
      local url = s.pictures[card.guid] or ""
      if UI.getAttribute("czs_image_" .. suffix, "image") ~= url then
        UI.setAttribute("czs_image_" .. suffix, "image", url)
      end
      UI.setAttribute("czs_image_" .. suffix, "color", url ~= "" and "#FFFFFF" or "#FFFFFF00")
      UI.setAttribute("czs_card_" .. suffix, "colors", card.guid == s.selected
        and "#244E46|#345E56|#244E46|#182331" or "#1C2939|#34485F|#244E46|#182331")
    else
      -- Clear stale faces as well as hiding them after a draw or search change.
      czsText("czs_name_" .. suffix, "")
      UI.setAttribute("czs_image_" .. suffix, "image", "")
    end
  end
  czsActive("czs_empty_" .. color, #filtered == 0)
  czsText("czs_count_" .. color, #filtered .. " cards · Page " .. s.page .. " / " .. pages)
  czsEnabled("czs_prev_" .. color, s.page > 1)
  czsEnabled("czs_next_" .. color, s.page < pages)
  czsEnabled("czs_take_" .. color, selected ~= nil and not s.busy)
  czsEnabled("czs_preview_take_" .. color, selected ~= nil and not s.busy)
end

local function czsCloseColor(color)
  CZS.state[color] = nil
  czsActive("czs_panel_" .. color, false)
  czsActive("czs_preview_" .. color, false)
  UI.setAttribute("czs_query_" .. color, "text", "")
  czsText("czs_status_" .. color, "")
  czsText("czs_preview_name_" .. color, "")
  UI.setAttribute("czs_preview_image_" .. color, "image", "")
  for i = 1, CZS.cells do
    czsText("czs_name_" .. i .. "_" .. color, "")
    UI.setAttribute("czs_image_" .. i .. "_" .. color, "image", "")
  end
end

local function czsRefresh(color, force)
  local s = CZS.state[color]
  if not s then return false end
  if s.owner ~= czsOwner(color) then czsCloseColor(color); return false end
  local deck = czsDeck(s)
  if not deck then czsCloseColor(color); return false end
  local ok, contents = pcall(function() return deck.getObjects() end)
  if not ok then czsCloseColor(color); return false end
  local cards = {}
  for _, meta in ipairs(contents) do
    if meta.guid and meta.guid ~= "" then
      local name = czsName(meta.name or meta.nickname)
      cards[#cards + 1] = {guid = meta.guid, name = name, key = czsKey(name)}
    end
  end
  table.sort(cards, function(a, b)
    if a.key ~= b.key then return a.key < b.key end
    -- Equal names use GUIDs, never deck positions (different printings too).
    return a.guid < b.guid
  end)
  local signature = {}
  for _, card in ipairs(cards) do signature[#signature + 1] = card.guid .. "\0" .. card.name end
  signature = table.concat(signature, "\1")
  if force or signature ~= s.signature then
    s.cards, s.signature, s.pictures = cards, signature, czsPictures(deck)
    czsRender(color)
  end
  return true
end

function czsOpen(color, deck)
  if not czsSeat(color) then return end
  if not deck or (deck.type ~= "Deck" and deck.tag ~= "Deck") then return end
  czsCloseColor(color)
  CZS.state[color] = {owner = czsOwner(color), deck = deck.getGUID(), query = "", page = 1,
                      cards = {}, shown = {}, pictures = {}}
  if czsRefresh(color, true) then
    czsActive("cz_panel_" .. color, false)
    czsActive("czs_panel_" .. color, true)
  end
end
function czsClose(player, _, id)
  if czsSession(player, id) then czsCloseColor(player.color) end
end
function czsSearch(player, value, id)
  local s = czsSession(player, id)
  if not s then return end
  s.query, s.page, s.selected = tostring(value or ""), 1, nil
  czsActive("czs_preview_" .. player.color, false)
  if czsRefresh(player.color) then czsRender(player.color) end
end
function czsClear(player, _, id)
  if not czsSession(player, id) then return end
  UI.setAttribute("czs_query_" .. player.color, "text", "")
  czsSearch(player, "", id)
end
function czsPage(player, direction, id)
  local s = czsSession(player, id)
  if not s then return end
  s.page = s.page + (direction == "next" and 1 or -1)
  if czsRefresh(player.color) then czsRender(player.color) end
end
function czsRefreshClick(player, _, id)
  if czsSession(player, id) then czsRefresh(player.color, true) end
end
function czsHidePreview(player, _, id)
  if czsSession(player, id) then czsActive("czs_preview_" .. player.color, false) end
end
function czsPick(player, value, id)
  local s = czsSession(player, id)
  if not s or s.busy then return end
  -- Remember what was actually drawn. Refresh must not reinterpret this slot
  -- as another card if somebody drew or shuffled in the meantime.
  local guid = tostring(value or "")
  local shown = false
  for _, visible in pairs(s.shown) do if visible == guid then shown = true end end
  if not shown then return end
  if not guid or not czsRefresh(player.color) then return end
  local selected = nil
  for _, card in ipairs(s.cards) do if card.guid == guid then selected = card end end
  if not selected then return end
  s.selected = guid
  local url = s.pictures[guid] or ""
  czsText("czs_status_" .. player.color, czsEscape(selected.name))
  czsText("czs_preview_name_" .. player.color, czsEscape(selected.name))
  UI.setAttribute("czs_preview_image_" .. player.color, "image", url)
  UI.setAttribute("czs_preview_image_" .. player.color, "color", url ~= "" and "#FFFFFF" or "#FFFFFF00")
  czsActive("czs_preview_" .. player.color, true)
  czsRender(player.color)
end
function czsTake(player, _, id)
  local s = czsSession(player, id)
  if not s or s.busy or not s.selected or not czsRefresh(player.color) then return end
  if not s.selected then return end
  local deck, guid = czsDeck(s), s.selected
  local hand = Player[player.color].getHandTransform()
  if not hand then czsText("czs_status_" .. player.color, "No hand zone is available."); return end
  s.busy = true
  czsRender(player.color)
  local ok, taken = pcall(function()
    return deck.takeObject({guid = guid, position = hand.position,
      rotation = {x = 0, y = hand.rotation.y, z = 180},
      smooth = false, callback_function = function(card)
        card.deal(1, player.color)
        if CZS.state[player.color] == s then
          s.busy, s.selected = false, nil
          czsActive("czs_preview_" .. player.color, false)
          czsText("czs_status_" .. player.color, "Card moved to your hand.")
          czsRefresh(player.color, true)
        end
      end})
  end)
  if not ok or not taken then
    s.busy = false
    czsText("czs_status_" .. player.color, "That card could not be taken. Refresh and try again.")
    czsRefresh(player.color, true)
  end
end

local function czsAttach(obj)
  if not obj or (obj.type ~= "Deck" and obj.tag ~= "Deck") then return end
  local guid = obj.getGUID()
  if CZS.attached[guid] == obj then return end
  CZS.attached[guid] = obj
  obj.addContextMenuItem("Search A–Z", function(color) czsOpen(color, obj) end)
end

-- Keep every base handler, and keep one copy of each wrapper on live reload.
CZS_BASE = CZS_BASE or {spawn = onObjectSpawn, destroy = onObjectDestroy, change = onPlayerChangeColor}
function onObjectSpawn(obj)
  if CZS_BASE.spawn then CZS_BASE.spawn(obj) end
  czsAttach(obj)
end
function onObjectDestroy(obj)
  if CZS_BASE.destroy then CZS_BASE.destroy(obj) end
  local guid = obj.getGUID()
  CZS.attached[guid] = nil
  for color, s in pairs(CZS.state) do if s.deck == guid then czsCloseColor(color) end end
end
function onPlayerChangeColor(color)
  if CZS_BASE.change then CZS_BASE.change(color) end
  for c, s in pairs(CZS.state) do
    if c == color or s.owner ~= czsOwner(c) then czsCloseColor(c) end
  end
end
Wait.frames(function()
  for _, obj in ipairs(getAllObjects()) do czsAttach(obj) end
end, 2)
-- Membership refresh also handles draws, joins, splitting and the deck collapsing
-- to one card. Sorting a copy means shuffling never changes the displayed order.
CZS.ticker = Wait.time(function()
  for color in pairs(CZS.state) do czsRefresh(color) end
end, 1, -1)
for _, color in ipairs(CZ.seats) do czsCloseColor(color) end
