-- Sleeve thumbnails load only when their chooser page is opened.
do
  local function asset(b)
    local url = b.thumb_url or b.thumb and CZ.base .. b.thumb
    return url and {name = "czsl_" .. b.id, url = url} or nil
  end
  local function register()
    local wanted = {}
    local sleeves = CZ.index and CZ.index.sleeves or {}
    for _, s in pairs(CZ.state) do
      if s.open and s.menu == "sleeve" then
        for i = 1, CZ.sleeveCells do
          local b = sleeves[((s.menuPage or 1) - 1) * CZ.sleeveCells + i]
          local a = b and asset(b)
          if a then wanted[a.name] = a end
        end
      end
    end
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
    if not changed then return true end
    if CZ.sleeveLoading then return false end
    table.sort(names)
    for _, name in ipairs(names) do merged[#merged + 1] = wanted[name] end
    CZ.sleeveLoading = true
    CZ.imageGeneration = (CZ.imageGeneration or 0) + 1
    UI.setCustomAssets(merged)
    local browser = CZ
    local function ready()
      if CZ ~= browser then return end
      CZ.sleeveLoading = false
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
    Wait.condition(ready, function() return not UI.loading end, 30, ready)
    return false
  end
  function czslRender(color)
    local s = CZ.state[color]
    if not s or not s.open or s.menu ~= "sleeve" then return end
    local sleeves = CZ.index.sleeves or {}
    local pages = math.max(1, math.ceil(#sleeves / CZ.sleeveCells))
    s.menuPage = math.max(1, math.min(s.menuPage or 1, pages))
    czUI("cz_menu_" .. color, "active", "False")
    czUI("cz_sleeves_" .. color, "active", "True")
    czUI("cz_scrim_" .. color, "active", "True")
    if not register() or UI.loading then
      if CZ.sleeveLoading or UI.loading then
        for i = 1, CZ.sleeveCells do czUI("cz_sl_" .. i .. "_" .. color, "interactable", "False") end
      end
      return
    end
    czUI("cz_sleeves_title_" .. color, "text", "Choose sleeves")
    for i = 1, CZ.sleeveCells do
      local b = sleeves[(s.menuPage - 1) * CZ.sleeveCells + i]
      local id = i .. "_" .. color
      czUI("cz_sl_" .. id, "active", b and "True" or "False")
      if b then
        czUI("cz_sl_" .. id, "interactable", "True")
        local a = asset(b)
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
