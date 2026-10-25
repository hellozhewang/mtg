-- Trigger areas and the stack panel.
--
-- A slide switch at each seat (built by build_tts_table.py, past that seat's row of
-- round buttons) marks a trigger area on that player's playmat, for everyone to see:
-- the far corner on the library side, boxed off by two lines in the seat's playmat
-- colour, with "TRIGGERS" in it. Off by default. Purely visual: the battle music
-- still counts the whole playmat. Each switch keeps its state in its own memo, which
-- saves and rewinds keep.
--
-- The stack panel on the edge strip is a picture laid on the table as a decal,
-- always shown, under the five snap points the builder adds.
--
-- Every other vector line and decal on the table is preserved: our lines are
-- recognised by their thickness, our decals by their name.
CZL = CZL or {}
CZL.guideThickness = 0.07
CZL.decalPrefix = "Cactuar "
-- The box: the far 53% of the mat's depth (leaving a row above the printed land line,
-- about 31% from the player's edge, for artifacts and such), across the 38% of its
-- width on the library side. Both from the owner's sketches on Blue's and White's mats.
CZL.depth, CZL.width = 0.53, 0.38
-- Playmat border colours (Tabletop Simulator's seat colours; White's mat is cream).
CZL.colors = {White = {0.92, 0.88, 0.78}, Red = {0.856, 0.1, 0.094}, Yellow = {0.905, 0.898, 0.172},
              Green = {0.192, 0.701, 0.168}, Blue = {0.118, 0.53, 1.0}, Purple = {0.627, 0.125, 0.941}}
-- Pictures from scripts/tabletop/make_table_art.py; the builder versions each URL.
CZL.labels = {White = "table/triggers-White.png", Red = "table/triggers-Red.png",
              Yellow = "table/triggers-Yellow.png", Green = "table/triggers-Green.png",
              Blue = "table/triggers-Blue.png", Purple = "table/triggers-Purple.png"}
CZL.labelSize = {5.6, 1.3}
-- Must match build_tts_table.stack_geometry() (tests/test_build_tts_table.py checks).
CZL.stack = {url = "table/stack-panel.png", x = 48.2, z = -4.6, width = 3.8, height = 22.3}
CZL.toggles = CZL.toggles or {}           -- seat colour -> its switch object

local function czlNear(a, b) return math.abs((tonumber(a) or 0) - b) < 0.0005 end
local function czlOurs(decal) return tostring(decal.name or ""):sub(1, #CZL.decalPrefix) == CZL.decalPrefix end
local function czlUrl(path) return ((CZ and CZ.base) or "") .. path end

-- The table's other vector lines and decals, as they are now (minus any of ours).
local function czlBaseLines()
  local keep = {}
  local ok, lines = pcall(function() return Global.getVectorLines() end)
  for _, line in ipairs(ok and lines or {}) do
    if not czlNear(line.thickness, CZL.guideThickness) then keep[#keep + 1] = line end
  end
  return keep
end

local function czlBaseDecals()
  local keep = {}
  local ok, decals = pcall(function() return Global.getDecals() end)
  for _, decal in ipairs(ok and decals or {}) do
    if not czlOurs(decal) then keep[#keep + 1] = decal end
  end
  return keep
end

-- A seat's playmat as a local frame. Local +z points at the player's own edge for
-- every seat (zone rotations are 0 or 180); TTS yaw rotates clockwise seen from above.
local function czlFrame(color)
  local seat = data and data[color]
  local zone = seat and seat.playmat
  if not zone then return nil end
  local ok, pos, scale, rot = pcall(function() return zone.getPosition(), zone.getScale(), zone.getRotation() end)
  if not ok or not pos then return nil end
  local yaw = math.rad(rot.y or 0)
  local frame = {w = scale.x, d = scale.z, yaw = rot.y or 0}
  function frame.world(lx, lz, y)
    return {x = pos.x + lx * math.cos(yaw) + lz * math.sin(yaw), y = y or 0.97,
            z = pos.z - lx * math.sin(yaw) + lz * math.cos(yaw)}
  end
  -- The library side: the side of the mat the seat's library zone sits on.
  frame.side = 1
  pcall(function()
    local lib = seat.libraryZone.getPosition()
    local dx, dz = lib.x - pos.x, lib.z - pos.z
    if dx * math.cos(yaw) - dz * math.sin(yaw) < 0 then frame.side = -1 end
  end)
  return frame
end

-- One seat's trigger area: its two lines (one polyline) and its label decal.
function czlGuides(color)
  local f = czlFrame(color)
  if not f then return {}, {} end
  local far = -f.d / 2
  local bottom = far + CZL.depth * f.d
  local outer = f.side * f.w / 2
  local inner = outer - f.side * CZL.width * f.w
  local line = {points = {f.world(inner, far), f.world(inner, bottom), f.world(outer, bottom)},
                color = CZL.colors[color] or {1, 1, 1}, thickness = CZL.guideThickness,
                rotation = {0, 0, 0}}
  local centre = f.world((inner + outer) / 2, (far + bottom) / 2, 0.975)
  local decal = {name = CZL.decalPrefix .. color .. " triggers", url = czlUrl(CZL.labels[color] or ""),
                 position = centre, rotation = {90, (f.yaw + 180) % 360, 0},
                 scale = {CZL.labelSize[1], CZL.labelSize[2], 1}}
  return {line}, {decal}
end

function czlStackDecal()
  local s = CZL.stack
  return {name = CZL.decalPrefix .. "stack", url = czlUrl(s.url), position = {s.x, 0.975, s.z},
          rotation = {90, 0, 0}, scale = {s.width, s.height, 1}}
end

-- Redraw: everything not ours, the stack panel, and the trigger areas switched on.
function czlDraw()
  local lines, decals = czlBaseLines(), czlBaseDecals()
  decals[#decals + 1] = czlStackDecal()
  for _, color in ipairs(CZ.seats) do
    if CZL.isOn(color) then
      local seatLines, seatDecals = czlGuides(color)
      for _, line in ipairs(seatLines) do lines[#lines + 1] = line end
      for _, decal in ipairs(seatDecals) do decals[#decals + 1] = decal end
    end
  end
  pcall(function() Global.setVectorLines(lines) end)
  pcall(function() Global.setDecals(decals) end)
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
