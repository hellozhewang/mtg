-- Private written guides. No picture assets or shared XML rebuilds.
CZ.guides = {}
do
  local function attr(id, key, value)
    if czUI then czUI(id, key, value) else UI.setAttribute(id, key, value) end
  end
  local function plain(value)
    return (tostring(value or ""):gsub("<", "‹"):gsub(">", "›"))
  end
  local function session(player, id)
    if not player then return nil end
    local seated = false
    for _, color in ipairs(CZ.seats) do if color == player.color then seated = true end end
    if not seated or id and id:match("_(%a+)$") ~= player.color then return nil end
    local s, who = CZ.state[player.color], nil
    pcall(function() who = Player[player.color].steam_id end)
    if s and s.player and who and s.player ~= who then return nil end
    return s
  end
  local function valid(payload, deck)
    if type(payload) ~= "table" or payload.v ~= 1 or payload.id ~= deck.id or type(payload.guide) ~= "table" then return false end
    for _, section in ipairs(payload.guide) do
      if type(section) ~= "table" or type(section.title) ~= "string" or type(section.rows) ~= "table" then return false end
      for _, row in ipairs(section.rows) do
        if type(row) ~= "table" or type(row.name) ~= "string" or type(row.text) ~= "string" then return false end
      end
    end
    return true
  end
  local function fetch(deck)
    local path = deck.preview
    if CZ.guides[path] then return CZ.guides[path] end
    local entry = {status = "loading"}
    CZ.guides[path] = entry
    WebRequest.get(CZ.base .. path, function(req)
      if CZ.guides[path] ~= entry then return end
      local ok, payload = false, nil
      if not req.is_error then ok, payload = pcall(JSON.decode, req.text) end
      if ok and valid(payload, deck) then
        entry.status, entry.sections = "ready", {}
        for _, section in ipairs(payload.guide) do
          local copy = {title = section.title, rows = {}}
          for _, row in ipairs(section.rows) do copy.rows[#copy.rows + 1] = {name = row.name, text = row.text} end
          entry.sections[#entry.sections + 1] = copy
        end
      else entry.status = "error" end
      for color, s in pairs(CZ.state) do
        if s.open and s.guideOpen and s.selected and s.selected.preview == path then czRender(color) end
      end
    end)
    return entry
  end
  local function content(sections)
    local lines, height = {}, 60
    local function add(value, heading)
      lines[#lines + 1] = (heading and "<b>" or "") .. plain(value:gsub(" %-> ", " → ")) .. (heading and "</b>" or "")
      for line in (value .. "\n"):gmatch("([^\n]*)\n") do height = height + math.max(1, math.ceil(#line / 55)) * 24 end
      height = height + 20
    end
    for _, section in ipairs(sections) do
      if section.title ~= "" then add(section.title, true) end
      for _, row in ipairs(section.rows) do
        if row.name ~= "" then add(row.name, true) end
        add(row.text, false)
      end
    end
    return table.concat(lines, "\n\n"), math.max(100, height)
  end
  function czgRender(color, s, deck)
    local path = deck and deck.preview
    if s.guideKey ~= path or s.guideDeck ~= (deck and deck.id) then
      s.guideKey, s.guideDeck = path, deck and deck.id
      s.guideOpen, s.guideDrawn = false, nil
    end
    local available = deck and deck.guide == true and path ~= nil
    if not available then s.guideOpen = false end
    attr("cz_guide_" .. color, "interactable", available and "True" or "False")
    attr("cz_guide_" .. color, "text", s.guideOpen and "Back to decks" or available and "Read guide" or "No guide")
    attr("cz_deck_list_" .. color, "active", s.guideOpen and "False" or "True")
    attr("cz_guide_view_" .. color, "active", s.guideOpen and "True" or "False")
    if not s.guideOpen then return end
    local entry = fetch(deck)
    attr("cz_guide_title_" .. color, "text", plain(deck.name) .. " · Guide")
    local signature = path .. ":" .. entry.status
    if s.guideDrawn == signature and s.guideGeneration == (CZ.imageGeneration or 0) then return end
    local text, height = "Loading guide…", 100
    if entry.status == "ready" then text, height = content(entry.sections)
    elseif entry.status == "error" then text = "Could not load the guide. Press Refresh to retry." end
    attr("cz_guide_text_" .. color, "text", text)
    attr("cz_guide_text_" .. color, "height", tostring(height))
    attr("cz_guide_text_" .. color, "preferredHeight", tostring(height))
    attr("cz_guide_content_" .. color, "height", tostring(height))
    attr("cz_guide_content_" .. color, "preferredHeight", tostring(height))
    s.guideDrawn, s.guideGeneration = signature, CZ.imageGeneration or 0
  end
  function czGuide(player, _, id)
    local s = session(player, id)
    if not s or not s.selected or not s.selected.guide or not s.selected.preview then return end
    s.guideOpen, s.guideDrawn = not s.guideOpen, nil
    czRender(player.color)
  end
  function czGuideClose(player, _, id)
    local s = session(player, id)
    if not s then return end
    s.guideOpen = false
    czRender(player.color)
  end
  function czgRefresh()
    for path, entry in pairs(CZ.guides) do if entry.status == "error" then CZ.guides[path] = nil end end
    for _, s in pairs(CZ.state) do s.guideDrawn = nil end
  end
end
