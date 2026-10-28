-- Sleeve thumbnails load only when their chooser page is opened.
do
  local function asset(b)
    local url = b.thumb_url or b.thumb and CZ.base .. b.thumb
    return url and {name = "czsl_" .. b.id, url = url} or nil
  end
  local pending = {}
  local register
  local browser = CZ
  local function current(color, request)
    local s = CZ.state[color]
    local who = Player[color] and Player[color].steam_id
    return s and s == request.state and s.open and s.menu == "sleeve"
      and s.menuPage == request.page and (not s.player or not who or s.player == who)
  end
  local function redraw()
    for _, c in ipairs(CZ.seats) do
      local s, who = CZ.state[c], Player[c] and Player[c].steam_id
      if s and s.open and (not s.player or not who or s.player == who) then
        czUI("cz_panel_" .. c, "active", "True")
        czUI("cz_search_" .. c, "text", s.query or "")
        czRender(c)
        if s.menu == "sleeve" then czslRender(c)
        else
          czUI("cz_sleeves_" .. c, "active", "False")
          if s.menu then czRenderMenu(c)
          else
            czUI("cz_menu_" .. c, "active", "False")
            czUI("cz_scrim_" .. c, "active", "False")
          end
        end
      else
        czUI("cz_panel_" .. c, "active", "False")
      end
    end
    if czsRedrawOpen then czsRedrawOpen() end
  end
  local function wait()
    CZ.sleeveLoading = true
    -- Asset changes and sprite rebuilding span native frames. Never bind a page
    -- in the frame that starts loading, or in the frame loading first goes false.
    Wait.frames(function()
      if CZ ~= browser then return end
      Wait.condition(function()
        Wait.frames(function()
          if CZ ~= browser then return end
          if UI.loading or CZ.pictureLoading or CZS and CZS.rebuilding then wait(); return end
          CZ.sleeveLoading = false
          -- A native rebuild can discard sprites while our write cache still
          -- remembers their names. Rebind after settling, even for cached pages.
          CZ.imageGeneration = (CZ.imageGeneration or 0) + 1
          register() -- Only explicit requests queued while the shared UI was loading.
          redraw()
        end, 2)
      end, function() return not UI.loading and not CZ.pictureLoading and not (CZS and CZS.rebuilding) end, 30, function()
        if CZ ~= browser then return end
        CZ.sleeveLoading, pending = false, {}
        CZ.imageGeneration = (CZ.imageGeneration or 0) + 1
        redraw() -- No automatic retry loop if the client's image loader is stuck.
      end)
    end, 1)
  end
  register = function()
    if CZ.sleeveLoading then return end
    local wanted = {}
    local sleeves = CZ.index and CZ.index.sleeves or {}
    for color, request in pairs(pending) do
      if current(color, request) then
        for i = 1, CZ.sleeveCells do
          local b = sleeves[(request.page - 1) * CZ.sleeveCells + i]
          local a = b and asset(b)
          if a then wanted[a.name] = a end
        end
      end
    end
    if not next(wanted) then pending = {}; return end
    if UI.loading or CZ.pictureLoading or CZS and CZS.rebuilding then wait(); return end
    pending = {}
    local merged, known = {}, {}
    for _, a in ipairs(UI.getCustomAssets() or {}) do
      known[a.name] = a.url
      if not wanted[a.name] then merged[#merged + 1] = a end
    end
    local names, changed = {}, false
    for name, a in pairs(wanted) do
      names[#names + 1] = name
      if known[name] ~= a.url then changed = true end
    end
    if not changed then return end
    table.sort(names)
    for _, name in ipairs(names) do merged[#merged + 1] = wanted[name] end
    CZ.imageGeneration = (CZ.imageGeneration or 0) + 1
    UI.setCustomAssets(merged)
    wait()
  end
  -- Only the Sleeves button and its pager may request pictures. Redrawing another
  -- player's open page after a shared asset update must never download that page.
  function czslRequest(color)
    czslRender(color) -- Clamp the requested page and immediately clear stale pictures.
    local s = CZ.state[color]
    if not s or not s.open or s.menu ~= "sleeve" then return end
    pending[color] = {state = s, page = s.menuPage}
    register()
    czslRender(color)
  end
  function czslRender(color)
    local s = CZ.state[color]
    if not s or not s.open or s.menu ~= "sleeve" then return end
    local sleeves = CZ.index.sleeves or {}
    local pages = math.max(1, math.ceil(#sleeves / CZ.sleeveCells))
    s.menuPage = math.max(1, math.min(s.menuPage or 1, pages))
    if czForgetUI then czForgetUI(color, "cz_sl_", "cz_sleeves_", "cz_menu_") end   -- see czForgetUI
    czUI("cz_menu_" .. color, "active", "False")
    czUI("cz_sleeves_" .. color, "active", "True")
    czUI("cz_scrim_" .. color, "active", "True")
    local known = {}
    if not CZ.sleeveLoading and not UI.loading then
      for _, a in ipairs(UI.getCustomAssets() or {}) do known[a.name] = a.url end
    end
    czUI("cz_sleeves_title_" .. color, "text", "Choose sleeves")
    for i = 1, CZ.sleeveCells do
      local b = sleeves[(s.menuPage - 1) * CZ.sleeveCells + i]
      local id = i .. "_" .. color
      czUI("cz_sl_" .. id, "active", b and "True" or "False")
      if b then
        czUI("cz_sl_" .. id, "interactable", (CZ.sleeveLoading or UI.loading) and "False" or "True")
        local a = asset(b)
        if a and known[a.name] ~= a.url then a = nil end
        czUI("cz_sl_img_" .. id, "image", a and a.name or "")
        czUI("cz_sl_img_" .. id, "color", a and "#FFFFFF" or "#FFFFFF00")
        czUI("cz_sl_name_" .. id, "text", (s.sleeve == b.id or not s.sleeve and b.id == "standard") and ("✓ " .. b.label) or b.label)
        czUI("cz_sl_" .. id, "colors", s.sleeve == b.id and "#1B3A33|#21483D|#163128|#1B2533" or "#202F42|#344D66|#275B4B|#182331")
      end
    end
    czUI("cz_sleeves_pager_" .. color, "active", pages > 1 and "True" or "False")
    czUI("cz_sleeves_page_" .. color, "text", s.menuPage .. " / " .. pages)
    czUI("cz_sleeves_prev_" .. color, "interactable", s.menuPage > 1 and "True" or "False")
    czUI("cz_sleeves_next_" .. color, "interactable", s.menuPage < pages and "True" or "False")
  end
  function czSleevePick(player, row)
    czChoose(player, row)
  end
end
