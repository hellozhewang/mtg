-- Website-style guide rows: one picture beside prose, combo strips above it.
-- Only this named VerticalLayout is replaced; the base table UI stays intact.
do
  local function escape(value)
    return (tostring(value or ""):gsub("&", "&amp;"):gsub('<', "&lt;"):gsub('>', "&gt;")
      :gsub('"', "&quot;"))
  end
  local function plain(value)
    return (tostring(value or ""):gsub("<", "‹"):gsub(">", "›"))
  end
  local function height(value, columns, size)
    local count = 0
    for line in (tostring(value or "") .. "\n"):gmatch("([^\n]*)\n") do
      -- Leave room for word wrapping rather than clipping a paragraph.
      count = count + math.max(1, math.ceil(#line / columns))
    end
    return count * (size + 6)
  end
  local function label(value, x, y, width, h, size, bold)
    return '<Text rectAlignment="UpperLeft" offsetXY="' .. x .. ' -' .. y
      .. '" width="' .. width .. '" height="' .. h .. '" fontSize="' .. size
      .. '" fontStyle="' .. (bold and 'Bold' or 'Normal')
      .. '" color="#E2E5EA" alignment="UpperLeft" horizontalOverflow="Wrap" raycastTarget="false" text="'
      .. escape(plain(value)) .. '"/>'
  end

  function czpGuideLayout(color, s, entry)
    if CZ.guideRebuilding or UI.loading then return false end
    local blocks, pictures, total, serial = {}, {}, 0, 0
    local function block(content, h, background)
      blocks[#blocks + 1] = '<Panel minHeight="' .. h .. '" preferredHeight="' .. h
        .. '" flexibleHeight="0" color="' .. (background or '#162130') .. '">' .. content .. '</Panel>'
      total = total + h + 10
    end
    local function picture(card, x, y, w, h)
      local face = card.faces and card.faces[1]
      local asset = face and CZ.previewAssets[face.FaceURL]
      if not asset then return label(card.name, x, y, w, h, 13) end
      serial = serial + 1
      local id = 'cz_guide_pic_' .. serial .. '_' .. color
      pictures[id] = {name = face.name, FaceURL = face.FaceURL, asset = asset}
      return '<Image id="' .. id .. '" rectAlignment="UpperLeft" offsetXY="' .. x .. ' -' .. y
        .. '" width="' .. w .. '" height="' .. h .. '" preserveAspect="true" color="#FFFFFF00"'
        .. ' onMouseEnter="czGuideHover" onMouseExit="czGuideUnhover" raycastTarget="true"/>'
    end
    if not entry or entry.status ~= 'ready' then
      local message = entry and entry.status == 'error' and 'Could not load the guide. Press Refresh to retry.' or 'Loading guide…'
      block(label(message, 0, 0, 536, 100, 16), 100)
    else
      for _, section in ipairs(entry.data.guide) do
        if section.title ~= '' then
          local h = height(section.title, 45, 19) + 12
          block(label(section.title, 0, 6, 536, h - 6, 19, true), h)
        end
        for _, row in ipairs(section.rows) do
          local cards, content, y, textWidth = row.cards or {}, '', 8, 520
          if #cards == 1 then
            content = picture(cards[1], 8, 8, 96, 134)
            textWidth = 408
          elseif #cards > 1 then
            for i, card in ipairs(cards) do
              local column, line = (i - 1) % 4, math.floor((i - 1) / 4)
              local x, top = 32 + column * 124, 8 + line * 136
              if i > 1 then
                content = content .. label(card.joiner == '->' and '→' or '+', x - 25, top + 48, 24, 32, 20, true)
              end
              content = content .. picture(card, x, top, 88, 123)
            end
            y = y + math.ceil(#cards / 4) * 136
          end
          local x = #cards == 1 and 116 or 8
          if row.name ~= '' then
            local h = height(row.name, #cards == 1 and 38 or 50, 17)
            content = content .. label(row.name:gsub(' %-> ', ' → '), x, y, textWidth, h, 17, true)
            y = y + h + 6
          end
          local h = height(row.text, #cards == 1 and 45 or 58, 16)
          content = content .. label(row.text, x, y, textWidth, h, 16)
          block(content, math.max(#cards == 1 and 150 or 0, y + h + 10), row.name ~= '' and '#1A2839' or nil)
        end
      end
    end
    local body = table.concat(blocks)
    s.guideCards = pictures
    if s.guideLayout == body then return true end
    local id = 'cz_guide_content_' .. color
    local replacement = '<VerticalLayout id="' .. id .. '" height="' .. math.max(100, total)
      .. '" preferredHeight="' .. math.max(100, total) .. '" spacing="10" childForceExpandHeight="false"'
      .. ' childForceExpandWidth="true">' .. body .. '</VerticalLayout>'
    -- MoonSharp rejects wildcard patterns over the table's large shared XML.
    -- Our content has no nested VerticalLayout, so use bounded plain searches.
    local xml = UI.getXml()
    local anchor = xml:find('id="' .. id .. '"', 1, true)
    if not anchor then return false end
    local start, scan = nil, 1
    while true do
      local p = xml:find('<VerticalLayout', scan, true)
      if not p or p > anchor then break end
      start, scan = p, p + 1
    end
    local finish = xml:find('</VerticalLayout>', anchor, true)
    if not start or not finish then return false end
    xml = xml:sub(1, start - 1) .. replacement .. xml:sub(finish + #'</VerticalLayout>')
    s.guideLayout, s.guidePainted = body, nil -- redraw will reuse the installed layout
    czGuideXml(xml)
    return false
  end
end
