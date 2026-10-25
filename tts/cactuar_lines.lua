-- Battlefield guide lines: a slide switch at each seat (built by build_tts_table.py,
-- next to that seat's row of round buttons) draws decorative divider lines on that
-- player's playmat, for everyone to see. Off by default. Purely visual: the battle
-- music still counts the whole playmat.
--
-- The playmat art already marks a land row along the player's edge (about the
-- nearest 31% of the mat). The guide adds one divider halfway through the rest,
-- splitting it into a creature row (toward the middle of the table) and a
-- noncreature-permanent row. Each switch keeps its state in its own memo, which
-- saves and rewinds keep. Every other vector line on the table (the edge-strip
-- stack area, anything the base draws) is preserved: guides are recognised by
-- their thickness.
CZL = CZL or {}
CZL.guideThickness = 0.05
CZL.color = {0.92, 0.88, 0.78}
CZL.toggles = CZL.toggles or {}           -- seat colour -> its switch object

local function czlNear(a, b) return math.abs((tonumber(a) or 0) - b) < 0.0005 end

-- The table's other vector lines, as they are now (minus any guides already drawn).
local function czlBaseLines()
  local keep = {}
  local ok, lines = pcall(function() return Global.getVectorLines() end)
  for _, line in ipairs(ok and lines or {}) do
    if not czlNear(line.thickness, CZL.guideThickness) then keep[#keep + 1] = line end
  end
  return keep
end

-- One seat's divider, in table space, from its playmat zone. Local +z points at the
-- player's own edge for every seat (zone rotations are 0 or 180).
function czlGuides(color)
  local seat = data and data[color]
  local zone = seat and seat.playmat
  if not zone then return {} end
  local ok, pos, scale, rot = pcall(function() return zone.getPosition(), zone.getScale(), zone.getRotation() end)
  if not ok or not pos then return {} end
  local yaw = math.rad(rot.y or 0)
  local function world(lx, lz)
    -- TTS yaw rotates clockwise seen from above.
    return {x = pos.x + lx * math.cos(yaw) + lz * math.sin(yaw), y = 0.97,
            z = pos.z - lx * math.sin(yaw) + lz * math.cos(yaw)}
  end
  local w, d = scale.x, scale.z
  local landEdge = d / 2 - 0.31 * d          -- the printed land line
  local divider = (landEdge + (-d / 2)) / 2  -- halfway across the rest of the mat
  local inset = 0.6
  return {{points = {world(-w / 2 + inset, divider), world(w / 2 - inset, divider)},
           color = CZL.color, thickness = CZL.guideThickness, rotation = {0, 0, 0}}}
end

-- Redraw: every non-guide line, plus the guides of each seat that has them on.
function czlDraw()
  local lines = czlBaseLines()
  for _, color in ipairs(CZ.seats) do
    if CZL.isOn(color) then
      for _, line in ipairs(czlGuides(color)) do lines[#lines + 1] = line end
    end
  end
  pcall(function() Global.setVectorLines(lines) end)
end

function CZL.isOn(color)
  local switch = CZL.toggles[color]
  local on = false
  pcall(function() on = switch.memo == "on" end)
  return on
end

-- A switch was clicked (from its own script: Global.call("czlToggle", {color = ...})).
function czlToggle(params)
  local color = params and params.color
  local switch = CZL.toggles[color]
  if not switch then return end
  local on = not CZL.isOn(color)
  pcall(function()
    switch.memo = on and "on" or "off"
    switch.call("czlShow", on)
  end)
  czlDraw()
end

-- Switches find themselves and register; once the playmats exist, draw.
function czlRegister(params)
  local color, switch = params and params.color, params and params.object
  if not color or not switch then return end
  CZL.toggles[color] = switch
  pcall(function() switch.call("czlShow", CZL.isOn(color)) end)
  if CZL.drawQueued then return end
  CZL.drawQueued = true
  Wait.condition(function() CZL.drawQueued = false; czlDraw() end,
    function() return data ~= nil and data.White ~= nil and data.White.playmat ~= nil end, 30,
    function() CZL.drawQueued = false end)
end
