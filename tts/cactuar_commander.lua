-- Commander rules only: no picture assets, guides, object spawns or XML rebuilds.
CZ.commanderTexts = CZ.commanderTexts or {}
do
  local browser = CZ
  local function plain(value)
    return (tostring(value or ""):gsub("<", "‹"):gsub(">", "›"))
  end
  local function format(commanders)
    local lines, height = {}, 12
    local function add(text, bold)
      lines[#lines + 1] = (bold and "<b>" or "") .. plain(text) .. (bold and "</b>" or "")
      for line in (text .. "\n"):gmatch("([^\n]*)\n") do
        height = height + math.max(1, math.ceil(#line / 39)) * 18
      end
    end
    for n, card in ipairs(commanders) do
      if n > 1 then add("") end
      add(card.name, true)
      if #card.faces > 1 then add("Front mana value (CMC): " .. tostring(card.mv)) end
      for _, face in ipairs(card.faces) do
        if #card.faces > 1 then add(face.name, true) end
        if #card.faces > 1 then
          if face.mana_cost ~= "" then add("Mana cost: " .. face.mana_cost) end
        else
          add((face.mana_cost ~= "" and face.mana_cost .. " · " or "") .. "Mana value (CMC): " .. tostring(card.mv))
        end
        add(face.type_line)
        if face.power ~= "" and face.toughness ~= "" then add("P/T: " .. face.power .. "/" .. face.toughness) end
        if face.loyalty ~= "" then add("Loyalty: " .. face.loyalty) end
        if face.defense ~= "" then add("Defense: " .. face.defense) end
        add(face.oracle_text)
      end
    end
    return table.concat(lines, "\n"), math.max(40, height)
  end
  local function valid(card)
    if type(card) ~= "table" or type(card.name) ~= "string" or type(card.mv) ~= "number"
      or type(card.faces) ~= "table" or #card.faces == 0 then return false end
    for _, face in ipairs(card.faces) do
      if type(face) ~= "table" then return false end
      for _, field in ipairs({"name", "mana_cost", "type_line", "oracle_text", "power", "toughness", "loyalty", "defense"}) do
        if type(face[field]) ~= "string" then return false end
      end
    end
    return true
  end
  local function fetch(deck)
    local key = deck.commander_text
    if CZ.commanderTexts[key] then return CZ.commanderTexts[key] end
    local entry = {status = "loading"}
    CZ.commanderTexts[key] = entry
    local function finish(cards)
      if CZ ~= browser or CZ.commanderTexts[key] ~= entry then return end
      entry.status = cards and "ready" or "error"
      if cards then entry.text, entry.height = format(cards) end
      for color, s in pairs(CZ.state) do
        local who = Player[color] and Player[color].steam_id
        if s.open and s.selected and s.selected.commander_text == key
          and (not s.player or not who or s.player == who) then czRender(color) end
      end
    end
    WebRequest.get(CZ.base .. key, function(req)
      if CZ ~= browser or CZ.commanderTexts[key] ~= entry then return end
      if req.is_error then finish(); return end
      local lines = {}
      for line in req.text:gmatch("[^\r\n]+") do lines[#lines + 1] = line end
      local position, cards, count = 1, {}, nil
      local function step()
        if CZ ~= browser or CZ.commanderTexts[key] ~= entry then return end
        local raw = lines[position]
        if not raw then finish(count == #cards and cards or nil); return end
        if #raw > 32768 then finish(); return end
        local ok, value = pcall(JSON.decode, raw)
        if not ok or type(value) ~= "table" then finish(); return end
        if position == 1 then
          if value.v ~= 1 or value.id ~= deck.id or type(value.count) ~= "number"
            or value.count < 1 or value.count % 1 ~= 0 or value.count ~= #lines - 1 then finish(); return end
          count = value.count
        else
          if not valid(value) then finish(); return end
          cards[#cards + 1] = value
        end
        position = position + 1
        Wait.frames(step, 1) -- Only the selected deck's small records, one per frame.
      end
      Wait.frames(step, 1)
    end)
    return entry
  end
  function czcRender(color, s, deck)
    if not s.open then return end
    czUI("cz_commander_" .. color, "active", deck and "True" or "False")
    if not deck then return end
    local entry = deck.commander_text and fetch(deck)
    local text, height = "Commander text unavailable. Refresh the deck list to check for updates.", 80
    if entry then
      if entry.status == "ready" then text, height = entry.text, entry.height
      elseif entry.status == "loading" then text = "Loading commander text…"
      else text = "Could not load commander text. Press Refresh to retry." end
    end
    czUI("cz_commander_text_" .. color, "text", text)
    czUI("cz_commander_text_" .. color, "preferredHeight", tostring(height))
    czUI("cz_commander_content_" .. color, "height", tostring(height))
    czUI("cz_commander_content_" .. color, "preferredHeight", tostring(height))
  end
  function czcRefresh()
    for key, entry in pairs(CZ.commanderTexts) do
      if entry.status == "error" then CZ.commanderTexts[key] = nil end
    end
  end
end
