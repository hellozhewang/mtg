-- Explicit commander pictures. Rendering/selection never queues image downloads.
-- Cache named assets by pinned URL; never replace shared XML at runtime.
do
  local browser, instance = CZ, {}
  CZ.pictureModule, CZ.pictureNames = instance, CZ.pictureNames or {}
  CZ.pictureSerial = CZ.pictureSerial or 0
  local pending, waiting = {}, false
  local register
  local function alive() return CZ == browser and CZ.pictureModule == instance end
  local function owner(color, s)
    local who = Player[color] and Player[color].steam_id
    return s and s.open and (not s.player or not who or s.player == who)
  end
  local function faces(s, deck)
    if s.pictureSource == (deck and deck.commanders) and s.pictureDeck == (deck and deck.id) then return s.pictureFaces or {} end
    s.pictureSource, s.pictureDeck = deck and deck.commanders, deck and deck.id
    s.pictureOpen, s.pictureIndex, s.pictureURL = false, 1, nil
    s.pictureFaces = {}
    for _, commander in ipairs(deck and deck.commanders or {}) do
      for _, face in ipairs(commander.faces or {}) do
        if type(face.FaceURL) == "string" and face.FaceURL:match("^https?://") then
          s.pictureFaces[#s.pictureFaces + 1] = {name = face.name or commander.name or "Commander", url = face.FaceURL}
        end
      end
    end
    return s.pictureFaces
  end
  local function current(color, r)
    local s = CZ.state[color]
    if not alive() or s ~= r.state or not owner(color, s) or not s.pictureOpen or not s.selected then return false end
    local list = faces(s, s.selected)
    local face = list[s.pictureIndex or 1]
    return s.pictureOpen and s.selected.id == r.deck and face and face.url == r.url
  end
  local function busy()
    -- Sleeves may be waiting for our load and set their loading flag meanwhile.
    -- They cannot start a native update while pictureLoading is true; do not
    -- wait for that flag here and create a mutual wait.
    return UI.loading or (not CZ.pictureLoading and CZ.sleeveLoading) or CZS and CZS.rebuilding
  end
  local function bind(color, s, face, sprite)
    local generation = CZ.imageGeneration or 0
    local bound = s.pictureBound
    if bound and bound.sprite == sprite and bound.generation == generation and bound.paint == CZ.uiPaint then return end
    local job = s.pictureBinding
    if job and job.sprite == sprite and job.generation == generation and job.paint == CZ.uiPaint then return end
    local id = "cz_picture_image_" .. color
    -- Native readiness alone can leave an already-named Image white. Force a
    -- real blank -> settled native frames -> sprite transition after readiness.
    -- Two frames can be only milliseconds on a fast client; also allow 0.2 s.
    local paint = CZ.uiPaint and CZ.uiPaint[id]
    if paint then paint.image = nil end
    czUI(id, "image", "")
    czUI(id, "color", "#FFFFFF00")
    local request = {state = s, deck = s.selected.id, url = face.url}
    job = {sprite = sprite, generation = generation, paint = CZ.uiPaint}
    s.pictureBinding, s.pictureBound = job, nil
    Wait.time(function()
      Wait.frames(function()
        if s.pictureBinding ~= job then return end
        s.pictureBinding = nil
        if not current(color, request) or CZ.pictureLoading or busy()
          or (CZ.imageGeneration or 0) ~= generation then return end
        czUI(id, "image", sprite)
        czUI(id, "color", "#FFFFFF")
        czUI("cz_picture_status_" .. color, "text", "")
        s.pictureBound = {sprite = sprite, generation = generation, paint = CZ.uiPaint}
      end, 2)
    end, 0.2)
  end
  local function redraw()
    if not alive() then return end
    for _, c in ipairs(CZ.seats) do
      local s = CZ.state[c]
      if owner(c, s) then
        czUI("cz_panel_" .. c, "active", "True")
        czUI("cz_search_" .. c, "text", s.query or "")
        czRender(c)
        if s.menu == "sleeve" and czslRender then czslRender(c)
        elseif s.menu and czRenderMenu then czRenderMenu(c) end
      else czUI("cz_panel_" .. c, "active", "False") end
    end
    if czsRedrawOpen then czsRedrawOpen() end
  end
  local function waitForUI(own)
    waiting = true
    Wait.frames(function()
      if not alive() then return end
      Wait.condition(function()
        Wait.frames(function()
          if not alive() then return end
          if busy() then waitForUI(own); return end
          waiting = false
          if own then
            CZ.pictureLoading = false
            CZ.imageGeneration = (CZ.imageGeneration or 0) + 1
          end
          register()
          redraw()
        end, 2)
      end, function() return not busy() end, 30, function()
        if not alive() then return end
        waiting, CZ.pictureLoading = false, false
        for c, r in pairs(pending) do if current(c, r) then r.state.pictureError = "Picture loading timed out. Close and try again." end end
        pending = {}
        CZ.imageGeneration = (CZ.imageGeneration or 0) + 1
        redraw()
      end)
    end, 1)
  end
  register = function()
    if not alive() or CZ.pictureLoading or waiting then return end
    local wanted = {}
    for c, r in pairs(pending) do
      if current(c, r) then wanted[r.url] = true else pending[c] = nil end
    end
    if not next(wanted) then return end
    if busy() then if not waiting then waitForUI(false) end; return end
    local merged, known = UI.getCustomAssets() or {}, {}
    for _, a in ipairs(merged) do
      if type(a.name) == "string" then
        local serial = a.name:match("^czcp_(%d+)$")
        if serial then
          CZ.pictureSerial = math.max(CZ.pictureSerial, tonumber(serial))
          known[a.url] = a.name
        end
      end
    end
    local changed = false
    for url in pairs(wanted) do
      if not known[url] then
        CZ.pictureSerial = CZ.pictureSerial + 1
        known[url] = "czcp_" .. CZ.pictureSerial
        merged[#merged + 1] = {name = known[url], url = url}
        changed = true
      end
      CZ.pictureNames[url] = known[url]
    end
    if not changed then pending = {}; return end
    -- All other modules' assets (including fonts, sleeves and Inspect) survive.
    CZ.pictureLoading = true
    CZ.imageGeneration = (CZ.imageGeneration or 0) + 1
    UI.setCustomAssets(merged)
    waitForUI(true)
  end
  local function session(player, id)
    if not player or id and id:match("_([%a]+)$") ~= player.color then return nil end
    local seat = false
    for _, c in ipairs(CZ.seats) do if player.color == c then seat = true end end
    local s = seat and CZ.state[player.color]
    if owner(player.color, s) and s.selected then return s end
  end
  local function request(color, s)
    local list = faces(s, s.selected)
    local face = list[s.pictureIndex or 1]
    if not face then return end
    s.pictureOpen, s.pictureURL, s.pictureError = true, face.url, nil
    pending[color] = {state = s, deck = s.selected.id, url = face.url}
    register()
    czcpRender(color, s, s.selected)
  end
  function czcpRender(color, s, deck)
    if not s.open then return end
    local list = faces(s, deck)
    if not s.pictureOpen then pending[color] = nil end
    czUI("cz_commander_show_" .. color, "interactable", #list > 0 and "True" or "False")
    czUI("cz_commander_show_" .. color, "text", s.pictureOpen and "Hide commander" or "Show commander")
    czUI("cz_commander_show_" .. color, "textColor", "#FFFFFF")
    czUI("cz_picture_" .. color, "active", s.pictureOpen and "True" or "False")
    local face = s.pictureOpen and list[s.pictureIndex or 1]
    if not face then
      s.pictureBinding, s.pictureBound = nil, nil
      czUI("cz_picture_image_" .. color, "image", "")
      return
    end
    local sprite = not CZ.pictureLoading and not busy() and not s.pictureError and CZ.pictureNames[face.url] or nil
    czUI("cz_picture_name_" .. color, "text", (face.name:gsub("<", "‹"):gsub(">", "›")))
    if not sprite then
      s.pictureBinding, s.pictureBound = nil, nil
      czUI("cz_picture_image_" .. color, "image", "")
      czUI("cz_picture_image_" .. color, "color", "#FFFFFF00")
    else bind(color, s, face, sprite) end
    czUI("cz_picture_status_" .. color, "text", s.pictureError or (s.pictureBound and "" or "Loading picture…"))
    czUI("cz_picture_page_" .. color, "text", (s.pictureIndex or 1) .. " / " .. #list)
    czUI("cz_picture_prev_" .. color, "interactable", (s.pictureIndex or 1) > 1 and "True" or "False")
    czUI("cz_picture_next_" .. color, "interactable", (s.pictureIndex or 1) < #list and "True" or "False")
  end
  function czPictureShow(player, _, id)
    local s = session(player, id)
    if not s then return end
    faces(s, s.selected)
    if s.pictureOpen then czPictureClose(player, nil, id) else request(player.color, s) end
  end
  function czPictureClose(player, _, id)
    local s = session(player, id)
    if not s then return end
    s.pictureOpen, s.pictureError = false, nil
    pending[player.color] = nil
    czcpRender(player.color, s, s.selected)
  end
  function czPictureReload(player, _, id)
    local s = session(player, id)
    if not s or not s.pictureOpen then return end
    -- Explicit recovery for native white sprites. Reuse the exact pinned URL;
    -- no cache-busting URL or whole shared-asset reload for a registered picture.
    s.pictureBinding, s.pictureBound = nil, nil
    request(player.color, s)
  end
  function czPictureStep(player, direction, id)
    local s = session(player, id)
    if not s or not s.pictureOpen or (direction ~= "prev" and direction ~= "next") then return end
    local list = faces(s, s.selected)
    local nextIndex = (s.pictureIndex or 1) + (direction == "next" and 1 or -1)
    if nextIndex < 1 or nextIndex > #list then return end
    s.pictureIndex = nextIndex
    request(player.color, s)
  end
end
