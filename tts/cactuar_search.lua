-- Alphabetical, private inspection of a live container. Sorting happens only in Lua's
-- copied metadata, never in the container. No deck indexes reach the UI.
-- Native Search has no scripted sort option: api.tabletopsimulator.com/behavior/container/
local czsPrevious = CZS
if czsPrevious and czsPrevious.ticker then Wait.stop(czsPrevious.ticker) end
if czsPrevious and czsPrevious.rebuildWait then Wait.stop(czsPrevious.rebuildWait) end
-- A full Global/browser reload can keep object references while native custom
-- menus are reset. Reuse registration flags only for an Inspect-only hot patch
-- in the same browser instance, never across a new CZ/global instance.
CZS = {state = {}, browser = CZ,
  attached = czsPrevious and czsPrevious.browser == CZ and czsPrevious.attached or {},
  cells = 32, capacity = {}, assets = {}, nextAsset = 0}
-- The build injects the same cell template used by the initial XML pool.
CZS.cellXml = [==[@INSPECT_CELL@]==]
for index, color in UI.getXml():gmatch('id="czs_card_(%d+)_(%a+)"') do
  CZS.capacity[color] = math.max(CZS.capacity[color] or CZS.cells, tonumber(index))
end

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
  return (text:gsub("<", "‹"):gsub(">", "›"))
end
local function czsName(text)
  local first = (text or ""):match("^[^\r\n]*") or ""
  first = first:gsub("%[%x%x%x%x%x%x%]", ""):gsub("%[%-%]", "")
  return first:match("%S") and first or "Unnamed object"
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
local function czsPlain(text)
  if type(text) ~= "string" then return "" end
  text = text:gsub("\r\n", "\n"):gsub("\r", "\n")
    :gsub("%[%x%x%x%x%x%x%]", ""):gsub("%[%-%]", "")
  local tags = {b = true, i = true, u = true, s = true, sub = true, sup = true, color = true, size = true}
  local function strip(tag, original)
    local name = tag:lower():match("^/?([%a]+)")
    if name == "br" then return "\n" end
    return tags[name] and "" or original
  end
  text = text:gsub("%[([^%]]+)%]", function(tag) return strip(tag, "[" .. tag .. "]") end)
  return (text:gsub("<([^>]+)>", function(tag) return strip(tag, "<" .. tag .. ">") end))
end
local function czsCardText(live, serialized)
  local parts, seen = {}, {}
  local function add(value)
    value = czsPlain(value)
    if value ~= "" then parts[#parts + 1] = value end
  end
  local function face(meta, current, depth)
    if type(meta) ~= "table" or seen[meta] or depth > 8 then return end
    seen[meta] = true
    current = current or meta
    add(current.name or current.nickname or current.Nickname or meta.Nickname)
    -- Some metadata providers shorten the live name; serialization can still
    -- carry the full nickname's type/mana-value lines.
    if current ~= meta and meta.Nickname ~= (current.name or current.nickname or current.Nickname) then add(meta.Nickname) end
    add(current.description or current.Description or meta.Description)
    add(current.type_line or current.TypeLine or meta.type_line or meta.TypeLine)
    add(current.oracle_text or current.OracleText or meta.oracle_text or meta.OracleText)
    local tags = {}
    for _, tag in ipairs(current.tags or current.Tags or meta.Tags or {}) do
      if type(tag) == "string" then tags[#tags + 1] = tag end
    end
    table.sort(tags)
    for _, tag in ipairs(tags) do add(tag) end
    local states = {}
    for id in pairs(meta.States or {}) do states[#states + 1] = id end
    table.sort(states, function(a, b) return tostring(a) < tostring(b) end)
    for _, id in ipairs(states) do face(meta.States[id], nil, depth + 1) end
  end
  -- Only visible names, descriptions, types and tags. Never GM notes, scripts,
  -- GUIDs, deck indexes, or the contents of a nested container.
  face(serialized, live, 0)
  return czsKey(table.concat(parts, "\n"))
end
local function czsIsContainer(obj)
  return obj and (obj.type == "Deck" or obj.tag == "Deck" or obj.type == "Bag" or obj.tag == "Bag")
end
local function czsDeck(s)
  local obj = getObjectFromGUID(s.deck)
  return czsIsContainer(obj) and obj or nil
end

local function czsImage(url)
  if type(url) ~= "string" then return nil end
  return url:match("^https?://") and url or nil
end
local function czsPicture(card, data)
  local key = math.floor((card.CardID or 0) / 100)
  local own, shared = card.CustomDeck or {}, data.CustomDeck or {}
  local sheet = own[tostring(key)] or own[key] or shared[tostring(key)] or shared[key]
  -- Atlas textures need UV cropping, which the Workshop Image element lacks.
  if sheet and (sheet.NumWidth or 1) == 1 and (sheet.NumHeight or 1) == 1 then
    return czsImage(sheet.FaceURL)
  elseif card.CustomImage and card.Name ~= "Custom_Dice" then
    return czsImage(card.CustomImage.ImageURL)
  end
  return nil
end

local czsRender, czsCloseColor
local function czsReload(change)
  CZS.rebuilding = true
  CZ.imageGeneration = (CZ.imageGeneration or 0) + 1
  change()
  CZS.rebuildWait = Wait.condition(function()
    CZS.rebuilding, CZS.rebuildWait = false, nil
    for _, c in ipairs(CZ.seats) do
      local s = CZS.state[c]
      if not s or s.owner ~= czsOwner(c) then
        czsCloseColor(c)
      else
        UI.setAttribute("czs_query_" .. c, "text", s.query)
        czsActive("czs_panel_" .. c, true)
      end
      if czRender and UI.getAttribute("cz_panel_" .. c, "active") == "True" then czRender(c) end
    end
    for _, c in ipairs(CZ.seats) do
      if CZS.rebuilding then break end
      czsRender(c)
    end
  end, function() return not UI.loading end)
end
local function czsRegisterPictures()
  -- Direct UI image URLs use a different decoder: the cache's WebP works as a
  -- named asset. Keep all other modules' assets and only our open views' faces.
  local wanted, merged, known, changed = {}, {}, {}, false
  for _, s in pairs(CZS.state) do
    for _, url in pairs(s.pictures) do wanted[url] = true end
  end
  for _, asset in ipairs(UI.getCustomAssets() or {}) do
    local serial = type(asset.name) == "string" and asset.name:match("^czsi_(%d+)$")
    if serial then
      CZS.nextAsset = math.max(CZS.nextAsset, tonumber(serial))
      if wanted[asset.url] then
        merged[#merged + 1] = asset; known[asset.url] = asset.name
      else changed = true end
    else merged[#merged + 1] = asset end
  end
  for url in pairs(wanted) do
    if not known[url] then
      CZS.nextAsset = CZS.nextAsset + 1
      local name = "czsi_" .. CZS.nextAsset
      merged[#merged + 1] = {name = name, url = url}
      known[url], changed = name, true
    end
  end
  CZS.assets = known
  if changed then czsReload(function() UI.setCustomAssets(merged) end); return false end
  return true
end
local function czsSprite(url) return url and CZS.assets[url] or "" end
local function czsHideZoom(color)
  czsActive("czs_zoom_" .. color, false)
  czsText("czs_zoom_name_" .. color, "")
  UI.setAttribute("czs_zoom_image_" .. color, "image", "")
end
local function czsRenderZoom(color)
  local s = CZS.state[color]
  if not s or s.owner ~= czsOwner(color) or s.previewOpen or CZS.rebuilding then
    czsHideZoom(color); return
  end
  local visible, card = false, nil
  for _, guid in ipairs(s.shown) do if guid == s.hovered then visible = true end end
  if visible then
    for _, candidate in ipairs(s.cards) do if candidate.guid == s.hovered then card = candidate end end
  end
  local sprite = card and czsSprite(s.pictures[card.guid]) or ""
  if not card or sprite == "" then czsHideZoom(color); return end
  czsText("czs_zoom_name_" .. color, czsEscape(card.name))
  UI.setAttribute("czs_zoom_image_" .. color, "image", sprite)
  UI.setAttribute("czs_zoom_image_" .. color, "color", "#FFFFFF")
  czsActive("czs_zoom_" .. color, true)
end
local function czsEnsureCells(color, count)
  local capacity = CZS.capacity[color] or CZS.cells
  if count <= capacity then return true end
  if CZS.rebuilding then return false end
  local size = math.ceil(count / 64) * 64
  local cells = {}
  for i = 1, size do
    cells[i] = CZS.cellXml:gsub("{I}", tostring(i)):gsub("{C}", color)
  end
  -- Replace only our grid in the serialized XML. Re-serializing the base UI's
  -- getXmlTable() loses entity escaping. Omit assets to preserve shared images.
  local xml, replaced = UI.getXml():gsub(
    '(<GridLayout[^>]-id="czs_grid_' .. color .. '"[^>]*>).-</GridLayout>',
    function(open) return open .. table.concat(cells) .. "</GridLayout>" end, 1)
  if replaced ~= 1 then return false end
  CZS.capacity[color] = size
  czsReload(function() UI.setXml(xml) end)
  return false
end
local function czsShort(text, limit)
  limit = limit or 15
  local chars = {}
  for char in text:gmatch("[%z\1-\127\194-\244][\128-\191]*") do chars[#chars + 1] = char end
  if #chars > limit then return table.concat(chars, "", 1, limit - 2) .. "…" end
  return text
end
czsRender = function(color)
  local s = CZS.state[color]
  if not s or CZS.rebuilding then return end
  local filtered, searchError = {}, nil
  if s.compiledQuery ~= s.query or s.compiledRegex ~= not not s.regex then
    s.compiledQuery, s.compiledRegex = s.query, not not s.regex
    if s.regex then s.matcher, s.patternError = CZRegex.compile(s.query, czsKey)
    else
      local query = czsKey(s.query)
      s.matcher, s.patternError = function(text) return text:find(query, 1, true) ~= nil end, nil
    end
  end
  searchError = s.patternError
  local budget = {remaining = 2000000}
  if not searchError then
    for _, card in ipairs(s.cards) do
      local matched, err = s.matcher(card.text, budget)
      if err then searchError = err; filtered = {}; break end
      if matched then filtered[#filtered + 1] = card end
    end
  end
  if not czsEnsureCells(color, #filtered) or not czsRegisterPictures() then return end
  s.shown = {}
  local selected = nil
  for _, card in ipairs(s.cards) do if card.guid == s.selected then selected = card end end
  if searchError then selected = nil end
  if not selected then s.selected, s.previewOpen = nil, false; czsActive("czs_preview_" .. color, false) end
  for i = 1, (CZS.capacity[color] or CZS.cells) do
    local card = filtered[i]
    local suffix = i .. "_" .. color
    czsActive("czs_card_" .. suffix, card ~= nil)
    if card then
      s.shown[i] = card.guid
      -- Bind stable identity into the client-side callback. A late click on an older
      -- view must never be reinterpreted as the new occupant of that slot.
      UI.setAttribute("czs_card_" .. suffix, "onClick", "czsPick(" .. card.guid .. ")")
      UI.setAttribute("czs_card_" .. suffix, "onMouseEnter", "czsHover(" .. card.guid .. ")")
      UI.setAttribute("czs_card_" .. suffix, "onMouseExit", "czsUnhover(" .. card.guid .. ")")
      czsText("czs_name_" .. suffix, czsEscape(czsShort(card.name)))
      UI.setAttribute("czs_card_" .. suffix, "tooltip", czsEscape(card.name))
      local url = czsSprite(s.pictures[card.guid])
      if UI.getAttribute("czs_image_" .. suffix, "image") ~= url then
        UI.setAttribute("czs_image_" .. suffix, "image", url)
      end
      UI.setAttribute("czs_image_" .. suffix, "color", url ~= "" and "#FFFFFF" or "#FFFFFF00")
      UI.setAttribute("czs_card_" .. suffix, "colors", card.guid == s.selected
        and "#181818|#202020|#181818|#010101" or "#010101|#101010|#181818|#010101")
    else
      -- Clear stale faces as well as hiding them after a draw or search change.
      czsText("czs_name_" .. suffix, "")
      UI.setAttribute("czs_image_" .. suffix, "image", "")
    end
  end
  czsActive("czs_empty_" .. color, #filtered == 0)
  czsText("czs_empty_" .. color, searchError and czsEscape(searchError) or "No matching objects.")
  czsText("czs_count_" .. color, searchError and czsEscape(searchError)
    or (#filtered .. " / " .. #s.cards .. " objects · A–Z" .. (s.regex and " · Regex" or "")))
  UI.setAttribute("czs_count_" .. color, "tooltip", czsEscape(searchError or "Searches stored names, types, descriptions, tags and alternate faces."))
  UI.setAttribute("czs_regex_" .. color, "colors", s.regex and "#305448|#3A6456|#244036|#222222" or "#242424|#383838|#181818|#242424")
  UI.setAttribute("czs_regex_" .. color, "tooltip", s.regex and "Regex on. Click for plain text. Examples: creature|artifact, draw.*card, \\belf\\b."
    or "Regex off. Click to enable: creature|artifact, draw.*card, \\belf\\b.")
  local height = math.max(1, math.ceil(#filtered / 4) * 134 + 8)
  UI.setAttribute("czs_grid_" .. color, "preferredHeight", tostring(height))
  UI.setAttribute("czs_grid_" .. color, "height", tostring(height))
  czsEnabled("czs_preview_take_" .. color, selected ~= nil and selected.physical and not s.busy)
  local deck = czsDeck(s)
  czsText("czs_preview_take_" .. color, selected and not selected.physical and "Preview only"
    or (deck and (deck.type == "Deck" or deck.tag == "Deck") and "Take to hand" or "Take out"))
  czsRenderZoom(color)
end

czsCloseColor = function(color)
  CZS.state[color] = nil
  czsHideZoom(color)
  czsActive("czs_panel_" .. color, false)
  czsActive("czs_preview_" .. color, false)
  UI.setAttribute("czs_query_" .. color, "text", "")
  czsText("czs_title_" .. color, "Inspect")
  czsText("czs_count_" .. color, "")
  czsText("czs_status_" .. color, "")
  czsText("czs_preview_name_" .. color, "")
  UI.setAttribute("czs_preview_image_" .. color, "image", "")
  for i = 1, (CZS.capacity[color] or CZS.cells) do
    czsText("czs_name_" .. i .. "_" .. color, "")
    UI.setAttribute("czs_card_" .. i .. "_" .. color, "tooltip", "")
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
  czsText("czs_title_" .. color, czsEscape(czsShort(czsName(deck.getName()), 32)))
  local dataOK, data = pcall(function() return deck.getData() end)
  data = dataOK and type(data) == "table" and data or {}
  -- Some importers leave every contained GUID empty. Serialized contents still
  -- provide names and textures; inspect those without assigning physical GUIDs
  -- or taking objects out to discover them. Neither path retains deck indexes.
  local liveByGUID, dataByGUID = {}, {}
  for _, meta in ipairs(contents) do if meta.guid and meta.guid ~= "" then liveByGUID[meta.guid] = meta end end
  local serialized = data.ContainedObjects
  for _, meta in ipairs(serialized or {}) do if meta.GUID and meta.GUID ~= "" then dataByGUID[meta.GUID] = meta end end
  if serialized and #serialized == #contents then contents = serialized end
  local cards, pictures = {}, {}
  for _, meta in ipairs(contents) do
    local guid = meta.GUID or meta.guid or ""
    local live = liveByGUID[guid] or meta
    local name = czsName(live.name or live.nickname or live.Nickname)
    local serializedCard = dataByGUID[guid] or meta
    local picture = czsPicture(serializedCard, data)
    local text = czsCardText(live, serializedCard)
    cards[#cards + 1] = {guid = guid, name = name, key = czsKey(name), picture = picture, text = text,
      physical = guid ~= "", identity = table.concat({name, meta.Name or "", tostring(meta.CardID or ""), picture or "", text}, "\0")}
  end
  table.sort(cards, function(a, b)
    if a.key ~= b.key then return a.key < b.key end
    if a.identity ~= b.identity then return a.identity < b.identity end
    return a.guid < b.guid
  end)
  local duplicates = {}
  for _, card in ipairs(cards) do
    if not card.physical then
      duplicates[card.identity] = (duplicates[card.identity] or 0) + 1
      local identity = card.identity .. "\1" .. duplicates[card.identity]
      if not s.tokens[identity] then
        s.nextToken = s.nextToken + 1
        s.tokens[identity] = "item" .. s.nextToken
      end
      card.guid = s.tokens[identity]
    end
    pictures[card.guid] = card.picture
  end
  local signature = {}
  for _, card in ipairs(cards) do signature[#signature + 1] = card.guid .. "\0" .. card.identity end
  signature = table.concat(signature, "\1")
  if force or signature ~= s.signature then
    s.cards, s.signature, s.pictures = cards, signature, pictures
    czsRender(color)
  end
  return true
end

function czsOpen(color, deck)
  if not czsSeat(color) then return end
  if not czsIsContainer(deck) then return end
  czsCloseColor(color)
  CZS.state[color] = {owner = czsOwner(color), deck = deck.getGUID(), query = "", regex = false,
                      cards = {}, shown = {}, pictures = {}, tokens = {}, nextToken = 0}
  if czsRefresh(color, true) then
    if czHideBrowser then czHideBrowser(color) else czsActive("cz_panel_" .. color, false) end
    czsActive("czs_panel_" .. color, true)
  end
end
function czsRedrawOpen()
  for color, s in pairs(CZS.state) do
    if s.owner ~= czsOwner(color) then czsCloseColor(color)
    else
      UI.setAttribute("czs_query_" .. color, "text", s.query)
      for i = 1, (CZS.capacity[color] or CZS.cells) do UI.setAttribute("czs_image_" .. i .. "_" .. color, "image", "") end
      if czsRefresh(color, true) then czsActive("czs_panel_" .. color, true) end
    end
  end
end
function czsClose(player, _, id)
  if czsSession(player, id) then czsCloseColor(player.color) end
end
function czsSearch(player, value, id)
  local s = czsSession(player, id)
  if not s then return end
  s.query, s.selected, s.hovered, s.previewOpen = tostring(value or ""), nil, nil, false
  czsHideZoom(player.color)
  czsActive("czs_preview_" .. player.color, false)
  if czsRefresh(player.color) then czsRender(player.color) end
end
function czsToggleRegex(player, _, id)
  local s = czsSession(player, id)
  if not s then return end
  s.regex = not s.regex
  czsSearch(player, s.query, id)
end
function czsClear(player, _, id)
  if not czsSession(player, id) then return end
  UI.setAttribute("czs_query_" .. player.color, "text", "")
  czsSearch(player, "", id)
end
function czsRefreshClick(player, _, id)
  if czsSession(player, id) then czsRefresh(player.color, true) end
end
function czsHidePreview(player, _, id)
  local s = czsSession(player, id)
  if s then s.previewOpen = false; czsActive("czs_preview_" .. player.color, false) end
end
function czsHover(player, value, id)
  local s = czsSession(player, id)
  if not s or s.busy then return end
  local guid = tostring(value or "")
  for _, shown in ipairs(s.shown) do
    if shown == guid then
      -- Browsing another thumbnail returns from the pinned click preview to hover.
      s.previewOpen, s.selected, s.hovered = false, nil, guid
      czsActive("czs_preview_" .. player.color, false)
      czsRenderZoom(player.color)
      return
    end
  end
end
function czsUnhover(player, value, id)
  local s = czsSession(player, id)
  -- A late exit from one cell must not hide a newer cell's zoom.
  if s and s.hovered == tostring(value or "") then
    s.hovered = nil; czsHideZoom(player.color)
  end
end
-- An older live session can still have v38's callback registered. Ignore that key;
-- fresh loads register no Inspect shortcut and zoom follows the pointer alone.
function czsZoomKey() end
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
  s.selected, s.previewOpen, s.hovered = guid, true, nil
  czsHideZoom(player.color)
  local url = czsSprite(s.pictures[guid])
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
  local selected
  for _, card in ipairs(s.cards) do if card.guid == s.selected then selected = card end end
  if not selected or not selected.physical then return end
  local deck, guid = czsDeck(s), s.selected
  local isDeck = deck.type == "Deck" or deck.tag == "Deck"
  local hand = isDeck and Player[player.color].getHandTransform() or nil
  if isDeck and not hand then czsText("czs_status_" .. player.color, "No hand zone is available."); return end
  local position = hand and hand.position or deck.getPosition() + Vector(3, 2, 0)
  s.busy = true
  czsRender(player.color)
  local ok, taken = pcall(function()
    return deck.takeObject({guid = guid, position = position,
      rotation = hand and {x = 0, y = hand.rotation.y, z = 180} or {x = 0, y = 0, z = 0},
      smooth = false, callback_function = function(card)
        if isDeck then card.deal(1, player.color) end
        if CZS.state[player.color] == s then
          s.busy, s.selected, s.previewOpen = false, nil, false
          czsActive("czs_preview_" .. player.color, false)
          czsText("czs_status_" .. player.color, isDeck and "Card moved to your hand." or "Object taken out.")
          czsRefresh(player.color, true)
        end
      end})
  end)
  if not ok or not taken then
    s.busy = false
    czsText("czs_status_" .. player.color, "That object could not be taken. Try again.")
    czsRefresh(player.color, true)
  end
end

local function czsAttach(obj)
  if not czsIsContainer(obj) then return end
  local guid = obj.getGUID()
  if CZS.attached[guid] == obj then return end
  local ok = pcall(function()
    obj.addContextMenuItem("Inspect", function(color) czsOpen(color, obj) end)
  end)
  if ok then CZS.attached[guid] = obj end
end

-- Keep every base handler, and keep one copy of each wrapper on live reload.
CZS_BASE = CZS_BASE or {spawn = onObjectSpawn, destroy = onObjectDestroy, change = onPlayerChangeColor}
function onObjectSpawn(obj)
  if CZS_BASE.spawn then CZS_BASE.spawn(obj) end
  czsAttach(obj)
  -- Native stack creation can report a card/unready object during spawn.
  -- One delayed retry covers merging/splitting without scanning every frame.
  local state = CZS
  Wait.frames(function()
    if CZS == state then pcall(czsAttach, obj) end
  end, 2)
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
local czsInstance = CZS
local function czsAttachExisting()
  if CZS ~= czsInstance then return end
  for _, obj in ipairs(getAllObjects()) do pcall(czsAttach, obj) end
end
Wait.frames(czsAttachExisting, 2)
Wait.frames(czsAttachExisting, 10) -- one startup retry for native menu readiness
-- Membership refresh also handles draws, joins, splitting and the deck collapsing
-- to one card. Sorting a copy means shuffling never changes the displayed order.
CZS.ticker = Wait.time(function()
  for color in pairs(CZS.state) do czsRefresh(color) end
end, 1, -1)
for _, color in ipairs(CZ.seats) do czsCloseColor(color) end
