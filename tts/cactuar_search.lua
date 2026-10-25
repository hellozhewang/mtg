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
  cells = 32, capacity = {}, assets = {}, nextAsset = 0, cache = {}, cacheSerial = 0, writes = {}}
-- The build injects the same cell template used by the initial XML pool.
CZS.cellXml = [==[@INSPECT_CELL@]==]
for index, color in UI.getXml():gmatch('id="czs_card_(%d+)_(%a+)"') do
  CZS.capacity[color] = math.max(CZS.capacity[color] or CZS.cells, tonumber(index))
end

-- Native UI calls and native serialization cannot be preempted. Bound the Lua
-- work between them, cancel stale jobs, and avoid resending unchanged attributes.
local function czsBatch(items, visit, done, current)
  local index = 1
  local function step()
    if not current() then return end
    local started, count = os.clock(), 0
    while index <= #items do
      visit(items[index], index)
      index, count = index + 1, count + 1
      if not current() then return end
      if count >= 8 or os.clock() - started >= 0.004 then break end
    end
    if index <= #items then Wait.frames(step, 1) else done() end
  end
  Wait.frames(step, 1)
end
local function czsAttr(id, key, value)
  local generation = CZ.imageGeneration or 0
  if CZS.writeGeneration ~= generation then CZS.writes, CZS.writeGeneration = {}, generation end
  local attrs = CZS.writes[id]
  if not attrs then attrs = {}; CZS.writes[id] = attrs end
  value = tostring(value)
  if attrs[key] ~= value then UI.setAttribute(id, key, value); attrs[key] = value end
end
local function czsText(id, text) czsAttr(id, "text", text or "") end
local function czsActive(id, active) czsAttr(id, "active", active and "True" or "False") end
local function czsEnabled(id, enabled) czsAttr(id, "interactable", enabled and "True" or "False") end
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
local czsAccents = { ["À"]="a", ["Á"]="a", ["Â"]="a", ["Ã"]="a", ["Ä"]="a", ["Å"]="a",
    ["à"]="a", ["á"]="a", ["â"]="a", ["ã"]="a", ["ä"]="a", ["å"]="a", ["Æ"]="ae", ["æ"]="ae",
    ["Ç"]="c", ["ç"]="c", ["È"]="e", ["É"]="e", ["Ê"]="e", ["Ë"]="e",
    ["è"]="e", ["é"]="e", ["ê"]="e", ["ë"]="e", ["Ì"]="i", ["Í"]="i", ["Î"]="i", ["Ï"]="i",
    ["ì"]="i", ["í"]="i", ["î"]="i", ["ï"]="i", ["Ñ"]="n", ["ñ"]="n",
    ["Ò"]="o", ["Ó"]="o", ["Ô"]="o", ["Õ"]="o", ["Ö"]="o", ["Ø"]="o",
    ["ò"]="o", ["ó"]="o", ["ô"]="o", ["õ"]="o", ["ö"]="o", ["ø"]="o", ["Œ"]="oe", ["œ"]="oe",
    ["Ù"]="u", ["Ú"]="u", ["Û"]="u", ["Ü"]="u", ["ù"]="u", ["ú"]="u", ["û"]="u", ["ü"]="u" }
local function czsKey(text)
  return string.lower((text:gsub("[\194-\244][\128-\191]*", czsAccents)))
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

local czsRender, czsCloseColor, czsHideZoom
local function czsReload(change)
  local instance = CZS
  CZS.rebuilding = true
  CZ.imageGeneration = (CZ.imageGeneration or 0) + 1
  change()
  -- Native loading may become true on the following frame. Bind sprites after
  -- loading and two settling frames, as in the demand-loaded sleeve chooser.
  local function waitReady()
    if CZS ~= instance then return end
    CZS.rebuildWait = Wait.condition(function()
      Wait.frames(function()
        if CZS ~= instance then return end
        if UI.loading then waitReady(); return end
        CZS.rebuilding, CZS.rebuildWait, CZS.writes = false, nil, {}
        CZ.imageGeneration = (CZ.imageGeneration or 0) + 1
        for _, c in ipairs(CZ.seats) do
          local s = CZS.state[c]
          if s and s.owner ~= czsOwner(c) then czsCloseColor(c)
          elseif s then
            czsAttr("czs_query_" .. c, "text", s.query)
            czsActive("czs_panel_" .. c, true)
            czsRender(c)
          else
            czsActive("czs_panel_" .. c, false)
            czsActive("czs_preview_" .. c, false)
            czsHideZoom(c)
          end
          if czRender and UI.getAttribute("cz_panel_" .. c, "active") == "True" then czRender(c) end
        end
      end, 2)
    end, function() return not UI.loading end)
  end
  Wait.frames(waitReady, 1)
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
  return changed and merged or true
end
local function czsSprite(url) return url and CZS.assets[url] or "" end
czsHideZoom = function(color)
  czsActive("czs_zoom_" .. color, false)
  czsText("czs_zoom_name_" .. color, "")
  czsAttr("czs_zoom_image_" .. color, "image", "")
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
  czsAttr("czs_zoom_image_" .. color, "image", sprite)
  czsAttr("czs_zoom_image_" .. color, "color", "#FFFFFF")
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
  -- MoonSharp rejects broad wildcard substitutions over the shared table XML.
  -- Locate our exact grid with plain searches; its card cells contain no grids.
  local xml = UI.getXml()
  local anchor = xml:find('id="czs_grid_' .. color .. '"', 1, true)
  if not anchor then return false end
  local start, scan = nil, 1
  while true do
    local pos = xml:find("<GridLayout", scan, true)
    if not pos or pos > anchor then break end
    start, scan = pos, pos + 1
  end
  local openEnd = start and xml:find(">", start, true)
  local closeStart = openEnd and xml:find("</GridLayout>", openEnd + 1, true)
  if not openEnd or openEnd < anchor or not closeStart then return false end
  xml = xml:sub(1, openEnd) .. table.concat(cells) .. xml:sub(closeStart)
  CZS.capacity[color] = size
  return xml
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
  if not s or CZS.rebuilding or CZ.pictureLoading then return end
  if s.readJob and not s.signature then return end
  if s.title then czsText("czs_title_" .. color, s.title) end
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
  local xml = czsEnsureCells(color, #filtered)
  if not xml then return end
  local assets = czsRegisterPictures()
  if xml ~= true or assets ~= true then
    -- One native rebuild for both a larger grid and its pictures. Preserve all
    -- other assets in the explicitly merged table; do not rebuild twice.
    czsReload(function()
      if xml ~= true then UI.setXml(xml, assets ~= true and assets or nil)
      else UI.setCustomAssets(assets) end
    end)
    return
  end
  s.shown = {}
  local selected = nil
  for _, card in ipairs(s.cards) do if card.guid == s.selected then selected = card end end
  if searchError then selected = nil end
  if not selected then s.selected, s.previewOpen = nil, false; czsActive("czs_preview_" .. color, false) end
  local instance, renderJob = CZS, {}
  s.renderJob = renderJob
  local cells = {}
  for i = 1, math.max(#filtered, s.painted or 0) do cells[i] = i end
  s.painted = math.max(s.painted or 0, #filtered)
  for i, card in ipairs(filtered) do s.shown[i] = card.guid end
  czsBatch(cells, function(i)
    local card = filtered[i]
    local suffix = i .. "_" .. color
    czsActive("czs_card_" .. suffix, card ~= nil)
    if card then
      s.shown[i] = card.guid
      -- Bind stable identity into the client-side callback. A late click on an older
      -- view must never be reinterpreted as the new occupant of that slot.
      czsAttr("czs_card_" .. suffix, "onClick", "czsPick(" .. card.guid .. ")")
      czsAttr("czs_card_" .. suffix, "onMouseEnter", "czsHover(" .. card.guid .. ")")
      czsAttr("czs_card_" .. suffix, "onMouseExit", "czsUnhover(" .. card.guid .. ")")
      czsText("czs_name_" .. suffix, czsEscape(czsShort(card.name)))
      czsAttr("czs_card_" .. suffix, "tooltip", czsEscape(card.name))
      local url = czsSprite(s.pictures[card.guid])
      czsAttr("czs_image_" .. suffix, "image", url)
      czsAttr("czs_image_" .. suffix, "color", url ~= "" and "#FFFFFF" or "#FFFFFF00")
      czsAttr("czs_card_" .. suffix, "colors", card.guid == s.selected
        and "#181818|#202020|#181818|#010101" or "#010101|#101010|#181818|#010101")
    else
      -- Clear stale faces as well as hiding them after a draw or search change.
      czsText("czs_name_" .. suffix, "")
      czsAttr("czs_image_" .. suffix, "image", "")
    end
  end, function()
    s.painted = #filtered
    czsActive("czs_grid_" .. color, true)
  end, function()
    return CZS == instance and CZS.state[color] == s and s.owner == czsOwner(color)
      and s.renderJob == renderJob and not CZS.rebuilding
  end)
  czsActive("czs_empty_" .. color, #filtered == 0)
  czsText("czs_empty_" .. color, searchError and czsEscape(searchError) or "No matching objects.")
  czsText("czs_count_" .. color, searchError and czsEscape(searchError)
    or (#filtered .. " / " .. #s.cards .. " objects · A–Z" .. (s.regex and " · Regex" or "")))
  czsAttr("czs_count_" .. color, "tooltip", czsEscape(searchError or "Searches stored names, types, descriptions, tags and alternate faces."))
  czsAttr("czs_regex_" .. color, "colors", s.regex and "#305448|#3A6456|#244036|#222222" or "#242424|#383838|#181818|#242424")
  czsAttr("czs_regex_" .. color, "tooltip", s.regex and "Regex on. Click for plain text. Examples: creature|artifact, draw.*card, \\belf\\b."
    or "Regex off. Click to enable: creature|artifact, draw.*card, \\belf\\b.")
  local height = math.max(1, math.ceil(#filtered / 4) * 134 + 8)
  czsAttr("czs_grid_" .. color, "preferredHeight", tostring(height))
  czsAttr("czs_grid_" .. color, "height", tostring(height))
  czsEnabled("czs_preview_take_" .. color, selected ~= nil and selected.physical and not s.busy)
  local deck = czsDeck(s)
  czsText("czs_preview_take_" .. color, selected and not selected.physical and "Preview only"
    or (deck and (deck.type == "Deck" or deck.tag == "Deck") and "Take to hand" or "Take out"))
  if s.previewOpen and selected then
    czsText("czs_preview_name_" .. color, czsEscape(selected.name))
    local sprite = czsSprite(s.pictures[selected.guid])
    czsAttr("czs_preview_image_" .. color, "image", sprite)
    czsAttr("czs_preview_image_" .. color, "color", sprite ~= "" and "#FFFFFF" or "#FFFFFF00")
    czsActive("czs_preview_" .. color, true)
  end
  czsRenderZoom(color)
end

czsCloseColor = function(color)
  local previous = CZS.state[color]
  local wasOpen = previous or UI.getAttribute("czs_panel_" .. color, "active") == "True"
  CZS.state[color] = nil
  if not wasOpen then
    czsActive("czs_panel_" .. color, false)
    czsActive("czs_preview_" .. color, false)
    czsHideZoom(color)
    return
  end
  czsHideZoom(color)
  czsActive("czs_panel_" .. color, false)
  czsActive("czs_preview_" .. color, false)
  czsAttr("czs_query_" .. color, "text", "")
  czsText("czs_title_" .. color, "Inspect")
  czsText("czs_count_" .. color, "")
  czsText("czs_status_" .. color, "")
  czsText("czs_preview_name_" .. color, "")
  czsAttr("czs_preview_image_" .. color, "image", "")
  local instance, cells = CZS, {}
  for i = 1, (previous and previous.painted or CZS.capacity[color] or CZS.cells) do cells[i] = i end
  czsBatch(cells, function(i)
    czsActive("czs_card_" .. i .. "_" .. color, false)
    czsText("czs_name_" .. i .. "_" .. color, "")
    czsAttr("czs_card_" .. i .. "_" .. color, "tooltip", "")
    czsAttr("czs_image_" .. i .. "_" .. color, "image", "")
  end, function() end, function() return CZS == instance and CZS.state[color] == nil end)
end

local function czsRefresh(color, force)
  local s = CZS.state[color]
  if not s then return false end
  if s.owner ~= czsOwner(color) then czsCloseColor(color); return false end
  local deck = czsDeck(s)
  if not deck then czsCloseColor(color); return false end
  if s.readJob and not force then return true end
  local instance, job = CZS, {}
  s.readJob = job
  local function current()
    return CZS == instance and CZS.state[color] == s and s.owner == czsOwner(color) and s.readJob == job
  end
  local function commit(raw)
    if not current() then return end
    if not force and s.raw == raw then s.readJob = nil; return end
    s.raw = raw
    local cards, pictures, duplicates, signature = {}, {}, {}, {}
    for _, source in ipairs(raw) do
      local card = source
      if not source.physical then
        card = {}; for k, v in pairs(source) do card[k] = v end
        duplicates[card.identity] = (duplicates[card.identity] or 0) + 1
        local identity = card.identity .. "\1" .. duplicates[card.identity]
        if not s.tokens[identity] then
          s.nextToken = s.nextToken + 1; s.tokens[identity] = "item" .. s.nextToken
        end
        card.guid = s.tokens[identity]
      end
      cards[#cards + 1], pictures[card.guid] = card, card.picture
      signature[#signature + 1] = card.guid .. "\0" .. card.identity
    end
    signature = table.concat(signature, "\1")
    s.readJob = nil
    if force or signature ~= s.signature then
      s.cards, s.signature, s.pictures = cards, signature, pictures
      czsRender(color)
    end
  end
  -- Start on a later frame so opening can display its loading state first.
  Wait.frames(function()
    if not current() then return end
    local ok, contents = pcall(function() return deck.getObjects() end)
    if not ok then czsCloseColor(color); return end
    s.title = czsEscape(czsShort(czsName(deck.getName()), 32))
    czsText("czs_title_" .. color, s.title)
    local fingerprints, liveByGUID = {}, {}
    czsBatch(contents, function(meta)
      local guid = meta.guid or meta.GUID or ""
      if guid ~= "" then liveByGUID[guid] = meta end
      fingerprints[#fingerprints + 1] = guid .. "\0" .. czsCardText(meta, meta)
    end, function()
      table.sort(fingerprints) -- membership/public text only; never indexes/order
      local fingerprint = table.concat(fingerprints, "\1")
      local cached = CZS.cache[s.deck]
      if cached and cached.object == deck and cached.fingerprint == fingerprint and not force then
        cached.polls = cached.polls + 1
        -- Infrequent serialization also detects image/alternate-face edits which
        -- getObjects does not expose. Explicit Refresh bypasses the cache.
        if cached.polls < 10 then commit(cached.cards); return end
      end
      local dataOK, data = pcall(function() return deck.getData() end)
      data = dataOK and type(data) == "table" and data or {}
      local serialized, dataByGUID = data.ContainedObjects, {}
      for _, meta in ipairs(serialized or {}) do
        if meta.GUID and meta.GUID ~= "" then dataByGUID[meta.GUID] = meta end
      end
      local source = serialized and #serialized == #contents and serialized or contents
      local cards = {}
      czsBatch(source, function(meta)
        local guid = meta.GUID or meta.guid or ""
        local live = liveByGUID[guid] or meta
        local name = czsName(live.name or live.nickname or live.Nickname)
        local serializedCard = dataByGUID[guid] or meta
        local picture = czsPicture(serializedCard, data)
        local text = czsCardText(live, serializedCard)
        cards[#cards + 1] = {guid = guid, name = name, key = czsKey(name), picture = picture, text = text,
          physical = guid ~= "", identity = table.concat({name, meta.Name or "", tostring(meta.CardID or ""), picture or "", text}, "\0")}
      end, function()
        table.sort(cards, function(a, b)
          if a.key ~= b.key then return a.key < b.key end
          if a.identity ~= b.identity then return a.identity < b.identity end
          return a.guid < b.guid
        end)
        CZS.cacheSerial = CZS.cacheSerial + 1
        CZS.cache[s.deck] = {object = deck, fingerprint = fingerprint, cards = cards, polls = 0, serial = CZS.cacheSerial}
        -- Retain at most six recently prepared containers, including closed ones.
        local count, oldest, serial = 0, nil, math.huge
        for guid, entry in pairs(CZS.cache) do
          count = count + 1
          if entry.serial < serial then oldest, serial = guid, entry.serial end
        end
        if count > 6 then CZS.cache[oldest] = nil end
        commit(cards)
      end, current)
    end, current)
  end, 1)
  return true
end

function czsOpen(color, deck)
  if not czsSeat(color) then return end
  if not czsIsContainer(deck) then return end
  -- Drop whatever the player had selected (the deck itself, usually), so table
  -- keys and drags don't act on it while they browse.
  pcall(function() Player[color].clearSelectedObjects() end)
  czsCloseColor(color)
  CZS.state[color] = {owner = czsOwner(color), deck = deck.getGUID(), query = "", regex = false,
                      cards = {}, shown = {}, pictures = {}, tokens = {}, nextToken = 0,
                      painted = CZS.capacity[color] or CZS.cells}
  czsActive("czs_grid_" .. color, false)
  czsActive("czs_empty_" .. color, false)
  czsText("czs_count_" .. color, "Reading contents…")
  if czsRefresh(color) then
    if czHideBrowser then czHideBrowser(color) else czsActive("cz_panel_" .. color, false) end
    czsActive("czs_panel_" .. color, true)
  end
end
function czsRedrawOpen()
  CZS.writes = {}
  for color, s in pairs(CZS.state) do
    if s.owner ~= czsOwner(color) then czsCloseColor(color)
    else
      czsAttr("czs_query_" .. color, "text", s.query)
      czsRender(color)
      czsActive("czs_panel_" .. color, true)
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
  czsRender(player.color)
end
function czsToggleRegex(player, _, id)
  local s = czsSession(player, id)
  if not s then return end
  s.regex = not s.regex
  czsSearch(player, s.query, id)
end
function czsClear(player, _, id)
  if not czsSession(player, id) then return end
  czsAttr("czs_query_" .. player.color, "text", "")
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
  czsAttr("czs_preview_image_" .. player.color, "image", url)
  czsAttr("czs_preview_image_" .. player.color, "color", url ~= "" and "#FFFFFF" or "#FFFFFF00")
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
  local okContents, contents = pcall(function() return deck.getObjects() end)
  local present = false
  if okContents then
    for _, meta in ipairs(contents) do if (meta.guid or meta.GUID) == guid then present = true; break end end
  end
  if not present then
    s.selected, s.previewOpen = nil, false
    czsActive("czs_preview_" .. player.color, false)
    czsRefresh(player.color, true)
    return
  end
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

-- An object's GUID, or nil: objects being destroyed or merged can report none, and
-- a nil table index is an error.
local function czsGuid(obj)
  local ok, guid = pcall(function() return obj.getGUID() end)
  if ok and guid ~= nil and guid ~= "" then return guid end
end

local function czsAttach(obj)
  if not czsIsContainer(obj) then return end
  local guid = czsGuid(obj)
  if not guid or CZS.attached[guid] == obj then return end
  local ok = pcall(function()
    obj.addContextMenuItem("Inspect", function(color) czsOpen(color, obj) end)
  end)
  if ok then CZS.attached[guid] = obj end
end

-- Keep every base handler, and keep one copy of each wrapper on live reload.
CZS_BASE = CZS_BASE or {spawn = onObjectSpawn, destroy = onObjectDestroy, change = onPlayerChangeColor}
if not CZS_BASE.zoneBound then
  CZS_BASE.enterZone, CZS_BASE.leaveZone = onObjectEnterZone, onObjectLeaveZone
  CZS_BASE.zoneBound = true
end
local function czsAfterZone(obj, rebuilt)
  -- The base's onObjectEnterZone/onObjectLeaveZone clear custom menus on normal
  -- cards/decks, then recreate their zone actions. Restore Inspect after them.
  if rebuilt and obj and obj.type == "Deck" and not obj.getName():lower():find("planechase") then
    local guid = czsGuid(obj)
    if guid then CZS.attached[guid] = nil end
  end
  pcall(czsAttach, obj)
end
function onObjectEnterZone(zone, obj)
  if CZS_BASE.enterZone then CZS_BASE.enterZone(zone, obj) end
  czsAfterZone(obj, CZS_BASE.enterZone ~= nil)
end
function onObjectLeaveZone(zone, obj)
  if CZS_BASE.leaveZone then CZS_BASE.leaveZone(zone, obj) end
  czsAfterZone(obj, CZS_BASE.leaveZone ~= nil)
end
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
  local guid = czsGuid(obj)
  if not guid then return end
  CZS.attached[guid], CZS.cache[guid] = nil, nil
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
