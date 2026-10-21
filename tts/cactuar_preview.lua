-- Readable pinned commander faces and deck guides for the private deck browser.
-- Small metadata files load on selection; browsing never spawns an object.
CZ.previews, CZ.previewAssets, CZ.previewSerial, CZ.previewSig = {}, {}, 0, ""
do
  local textColor, dim = "#E2E5EA", "#C0C8D2"
  local function text(id, value) UI.setAttribute(id, "text", value or "") end
  local function active(id, value) UI.setAttribute(id, "active", value and "True" or "False") end
  local function enabled(id, value) UI.setAttribute(id, "interactable", value and "True" or "False") end
  local function button(id, value) text(id, "<color=" .. textColor .. ">" .. value .. "</color>") end
  local function plain(value)
    return (tostring(value or ""):gsub("<", "‹"):gsub(">", "›"))
  end
  local function key(deck) return deck and deck.preview end
  local function session(player, id)
    if not player then return nil end
    local color, seated = player.color, false
    for _, c in ipairs(CZ.seats) do if c == color then seated = true end end
    if not seated or id and id:match("_([%a]+)$") ~= color then return nil end
    local s = CZ.state[color]
    local who
    pcall(function() who = Player[color].steam_id end)
    if s and s.player and who and s.player ~= who then return nil end
    return s
  end
  local function notify(path)
    for color, s in pairs(CZ.state) do
      if s.selected and key(s.selected) == path then czRender(color) end
    end
  end
  local function valid(payload, deck)
    if type(payload) ~= "table" or payload.v ~= 1 or payload.id ~= deck.id
        or type(payload.commanders) ~= "table" or #payload.commanders == 0 or #payload.commanders > 2
        or type(payload.guide) ~= "table" then return false end
    for _, commander in ipairs(payload.commanders) do
      if type(commander) ~= "table" or type(commander.name) ~= "string" or type(commander.faces) ~= "table" or #commander.faces == 0 then return false end
      for _, face in ipairs(commander.faces) do
        if type(face) ~= "table" or type(face.name) ~= "string" or type(face.FaceURL) ~= "string" or not face.FaceURL:match("^https?://") then return false end
      end
    end
    for _, section in ipairs(payload.guide) do
      if type(section) ~= "table" or type(section.title) ~= "string" or type(section.rows) ~= "table" then return false end
      for _, row in ipairs(section.rows) do
        if type(row) ~= "table" or type(row.name) ~= "string" or type(row.text) ~= "string" then return false end
        if row.cards ~= nil then
          if type(row.cards) ~= "table" then return false end
          for _, card in ipairs(row.cards) do
            if type(card) ~= "table" or type(card.name) ~= "string" or type(card.faces) ~= "table"
                or (card.joiner ~= "" and card.joiner ~= "+" and card.joiner ~= "->") then return false end
            for _, face in ipairs(card.faces) do
              if type(face) ~= "table" or type(face.name) ~= "string" or type(face.FaceURL) ~= "string"
                  or not face.FaceURL:match("^https?://") then return false end
            end
          end
        end
      end
    end
    return true
  end
  local function fetch(deck)
    local path = key(deck)
    if not path then return nil end -- older indexes remain usable for loading decks
    if CZ.previews[path] then return CZ.previews[path] end
    local entry = {status = "loading"}
    CZ.previews[path] = entry
    WebRequest.get(CZ.base .. path, function(req)
      -- A refresh may have discarded a failed request or installed a newer entry.
      if CZ.previews[path] ~= entry then return end
      local ok, payload = false, nil
      if not req.is_error then ok, payload = pcall(JSON.decode, req.text) end
      if ok and valid(payload, deck) then entry.status, entry.data = "ready", payload
      else entry.status = "error" end
      notify(path) -- draw the currently selected deck, never a stale response's deck
    end)
    return entry
  end

  local function registerPictures()
    local wanted = {}
    for _, s in pairs(CZ.state) do
      local entry = s.selected and CZ.previews[key(s.selected)]
      if s.open and entry and entry.status == "ready" then
        for _, commander in ipairs(entry.data.commanders) do
          for _, face in ipairs(commander.faces) do wanted[face.FaceURL] = true end
        end
        if s.guideOpen then
          for _, section in ipairs(entry.data.guide) do
            for _, row in ipairs(section.rows) do
              for _, card in ipairs(row.cards or {}) do
                local face = card.faces[1]
                if face then wanted[face.FaceURL] = true end
              end
            end
          end
        end
      end
    end
    local urls = {}
    for url in pairs(wanted) do urls[#urls + 1] = url end
    table.sort(urls)
    local signature = table.concat(urls, "\n")
    if signature == CZ.previewSig then return true end
    local merged, known = {}, {}
    for _, asset in ipairs(UI.getCustomAssets() or {}) do
      local n = type(asset.name) == "string" and asset.name:match("^czcp_(%d+)$")
      if n then
        CZ.previewSerial = math.max(CZ.previewSerial, tonumber(n))
        if wanted[asset.url] then merged[#merged + 1] = asset; known[asset.url] = asset.name end
      else merged[#merged + 1] = asset end
    end
    for _, url in ipairs(urls) do
      if not known[url] then
        CZ.previewSerial = CZ.previewSerial + 1
        known[url] = "czcp_" .. CZ.previewSerial
        merged[#merged + 1] = {name = known[url], url = url}
      end
    end
    CZ.previewAssets, CZ.previewSig = known, signature
    czSetAssets(merged) -- preserve sleeves, Inspect faces and every base asset
    return false -- render again after the rebuilt UI and its assets are ready
  end

  local function paintImages(color, s, images, counter)
    s[counter] = (s[counter] or 0) + 1
    local paint = s[counter]
    for id in pairs(images) do
      UI.setAttribute(id, "image", "")
      UI.setAttribute(id, "color", "#FFFFFF00")
    end
    local function current()
      return CZ.state[color] == s and s.open and s[counter] == paint
        and not UI.loading and session(Player[color]) == s
        and (counter ~= "guidePaint" or s.guideOpen)
    end
    local function bind()
      if not current() then return end
      for id, asset in pairs(images) do
        UI.setAttribute(id, "image", asset)
        UI.setAttribute(id, "color", asset ~= "" and "#FFFFFF" or "#FFFFFF00")
      end
    end
    Wait.frames(bind, 2)
    Wait.time(function()
      if not current() then return end
      for id in pairs(images) do UI.setAttribute(id, "image", "") end
      Wait.frames(bind, 2)
    end, 1)
  end

  local function guideText(guide)
    local lines, rows = {}, 2
    local function add(value, prefix, suffix, heading)
      local escaped = plain(value)
      lines[#lines + 1] = (prefix or "") .. escaped .. (suffix or "")
      local current = 0
      -- Conservative wrapping estimate for the fixed 562px reading column.
      -- The final padding prevents the last paragraph being clipped.
      for line in (tostring(value) .. "\n"):gmatch("([^\n]*)\n") do
        current = current + math.max(1, math.ceil(#line / (heading and 45 or 56)))
      end
      rows = rows + current + 1
    end
    for _, section in ipairs(guide) do
      if section.title ~= "" then add(section.title, "<size=19><b>", "</b></size>", true) end
      for _, row in ipairs(section.rows) do
        if row.name ~= "" then add(row.name, "<b><color=" .. textColor .. ">", "</color></b>", true) end
        if row.text ~= "" then add(row.text) end
      end
    end
    return table.concat(lines, "\n\n"), rows * 25 + 48
  end

  function czpRender(color, s, deck)
    local path = key(deck)
    if s.previewKey ~= path or s.previewDeck ~= (deck and deck.id) then
      s.previewKey, s.previewDeck = path, deck and deck.id
      s.commander, s.commanderFace, s.guideOpen, s.guideDrawn = 1, 1, false, nil
      s.guideHover, s.guideCards = nil, nil
    end
    local entry = deck and fetch(deck)
    local payload = entry and entry.status == "ready" and entry.data or nil
    if not registerPictures() or UI.loading then return end
    local commanders = payload and payload.commanders or {}
    s.commander = math.max(1, math.min(s.commander or 1, math.max(1, #commanders)))
    local commander = commanders[s.commander]
    local faces = commander and commander.faces or {}
    s.commanderFace = math.max(1, math.min(s.commanderFace or 1, math.max(1, #faces)))
    local face = s.guideOpen and s.guideHover or faces[s.commanderFace]
    local image = face and CZ.previewAssets[face.FaceURL] or ""
    -- TTS can keep a blank sprite when clearing and rebinding in one frame,
    -- even after UI.loading becomes false. Let the clear reach the renderer.
    paintImages(color, s, {["cz_commander_image_" .. color] = image}, "previewPaint")
    text("cz_commander_name_" .. color, face and plain(face.name) or "Commander preview")
    local note = not deck and "Select a deck to read its commander."
      or not path and "Press Refresh to get commander previews."
      or entry.status == "error" and "Could not load the preview.\nPress Refresh to retry."
      or "Loading commander…"
    text("cz_commander_note_" .. color, note)
    active("cz_commander_note_" .. color, image == "")
    text("cz_commander_page_" .. color, s.guideHover and "Guide card" or commander and ("Commander " .. s.commander .. " / " .. #commanders) or "")
    enabled("cz_commander_prev_" .. color, s.commander > 1)
    enabled("cz_commander_next_" .. color, s.commander < #commanders)
    active("cz_commander_flip_" .. color, #faces > 1 and not s.guideHover)
    button("cz_commander_prev_" .. color, "‹")
    button("cz_commander_next_" .. color, "›")
    button("cz_commander_flip_" .. color, s.commanderFace > 1 and "Front" or "Flip")

    local hasGuide = deck and (deck.guide == true or payload and #payload.guide > 0)
    enabled("cz_guide_" .. color, hasGuide == true)
    button("cz_guide_" .. color, s.guideOpen and "Back to decks" or hasGuide and "Read guide" or "No guide")
    if not deck or not hasGuide then s.guideOpen = false end
    active("cz_deck_list_" .. color, not s.guideOpen)
    active("cz_guide_view_" .. color, s.guideOpen)
    if s.guideOpen then
      text("cz_guide_title_" .. color, "Deck guide")
      UI.setAttribute("cz_guide_title_" .. color, "tooltip", plain(deck.name .. " · " .. deck.commander))
      button("cz_guide_back_" .. color, "Back to decks")
      if czpGuideLayout then
        if not czpGuideLayout(color, s, entry) then return end
        local images, signature = {}, {}
        for id, card in pairs(s.guideCards or {}) do
          images[id] = card.asset; signature[#signature + 1] = id .. "=" .. card.asset
        end
        table.sort(signature)
        signature = table.concat(signature, ";")
        if s.guidePainted ~= signature then
          s.guidePainted = signature
          paintImages(color, s, images, "guidePaint")
        end
      elseif s.guideDrawn ~= entry then
        local content, height = "Loading guide…", 100
        if entry and entry.status == "ready" then content, height = guideText(payload.guide)
        elseif entry and entry.status == "error" then content = "Could not load the guide. Press Refresh to retry." end
        text("cz_guide_text_" .. color, content)
        UI.setAttribute("cz_guide_text_" .. color, "height", tostring(height))
        UI.setAttribute("cz_guide_text_" .. color, "preferredHeight", tostring(height))
        -- Loading -> ready mutates the same entry; cache status as well.
        s.guideDrawn, s.guideStatus = entry, entry and entry.status
      elseif s.guideStatus ~= (entry and entry.status) then
        s.guideDrawn = nil
        czpRender(color, s, deck)
      end
    end
  end

  function czCommander(player, direction, id)
    local s = session(player, id)
    if not s or not s.selected then return end
    local entry = CZ.previews[key(s.selected)]
    if not entry or entry.status ~= "ready" then return end
    s.guideHover = nil
    local count = #entry.data.commanders
    if direction == "flip" then
      local commander = entry.data.commanders[s.commander or 1]
      s.commanderFace = (s.commanderFace or 1) % #commander.faces + 1
    elseif direction == "next" or direction == "prev" then
      s.commander = math.max(1, math.min(count, (s.commander or 1) + (direction == "next" and 1 or -1)))
      s.commanderFace = 1
    else return end
    czRender(player.color)
  end
  function czGuide(player, _, id)
    local s = session(player, id)
    if not s or not s.selected then return end
    local entry = CZ.previews[key(s.selected)]
    if not s.selected.guide and not (entry and entry.data and #entry.data.guide > 0) then return end
    s.guideOpen, s.guideDrawn = not s.guideOpen, nil
    s.guidePainted = nil
    s.guideHover = nil
    czRender(player.color)
  end
  function czGuideClose(player, _, id)
    local s = session(player, id)
    if not s then return end
    s.guideOpen = false
    s.guideHover = nil
    czRender(player.color)
  end
  function czGuideHover(player, _, id)
    local s = session(player, id)
    local card = s and s.guideOpen and s.guideCards and s.guideCards[id]
    if not card then return end
    s.guideHover, s.guideHoverId = card, id
    czRender(player.color)
  end
  function czGuideUnhover(player, _, id)
    local s = session(player, id)
    if not s or s.guideHoverId ~= id then return end
    s.guideHover, s.guideHoverId = nil, nil
    czRender(player.color)
  end
  function czpRefresh()
    for path, entry in pairs(CZ.previews) do if entry.status == "error" then CZ.previews[path] = nil end end
    for _, s in pairs(CZ.state) do s.guideDrawn = nil end
  end
end
