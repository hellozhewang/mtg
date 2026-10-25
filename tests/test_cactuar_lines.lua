-- Trigger areas and the stack panel (tts/cactuar_lines.lua) against stand-ins for Tabletop Simulator.
local checks, failures = 0, 0
local function check(value, message)
  checks = checks + 1
  if not value then failures = failures + 1; print("FAIL: " .. message) end
end
local function near(a, b) return math.abs(a - b) < 0.01 end
local function at(p, x, z) return near(p.x, x) and near(p.z, z) end

CZ = {seats = {"White", "Red", "Yellow", "Green", "Blue", "Purple"}, base = "https://x/tts/"}
-- The real table's playmat zones (south seats face 180, north seats 0), each with its
-- library column on the player's right.
local mats = {White = {27.3, -14.9, 180}, Red = {-2.1, -14.9, 180}, Yellow = {-31.5, -14.9, 180},
              Green = {-27.3, 14.9, 0}, Blue = {2.1, 14.9, 0}, Purple = {31.5, 14.9, 0}}
local function zone(x, z, sx, sz, yaw)
  return {getPosition = function() return {x = x, y = 1, z = z} end,
          getScale = function() return {x = sx, y = 1, z = sz} end,
          getRotation = function() return {x = 0, y = yaw, z = 0} end}
end
data = {}
for color, m in pairs(mats) do
  local right = m[3] == 180 and 14.45 or -14.45
  data[color] = {playmat = zone(m[1], m[2], 24.8, 22.0, m[3]),
                 libraryZone = zone(m[1] + right, m[2] - 5.2 * (m[3] == 180 and 1 or -1), 2.1, 3.1, m[3])}
end
-- Somebody else's line and decal are already on the table.
local otherLine = {points = {{x = 0, y = 0.97, z = 0}, {x = 1, y = 0.97, z = 0}}, thickness = 0.1}
local otherDecal = {name = "Someone's logo", url = "https://y/logo.png", position = {0, 1, 0}}
local drawn, decals = {otherLine}, {otherDecal}
Global = {getVectorLines = function() return drawn end, setVectorLines = function(l) drawn = l end,
          getDecals = function() return decals end, setDecals = function(d) decals = d end}
Wait = {condition = function(fn, ready) if ready() then fn() end end}
local function switch()
  local s = {memo = "off", shown = nil}
  s.call = function(fn, on) if fn == "czlShow" then s.shown = on end end
  return s
end
local function ours(kind)
  local n = 0
  for _, l in ipairs(drawn) do if kind == "lines" and near(l.thickness, 0.07) then n = n + 1 end end
  for _, d in ipairs(decals) do if kind == "decals" and tostring(d.name):find("^Cactuar ") then n = n + 1 end end
  return n
end
local function decal(name) for _, d in ipairs(decals) do if d.name == name then return d end end end

dofile("tts/cactuar_lines.lua")
local switches = {}
for _, color in ipairs(CZ.seats) do
  switches[color] = switch()
  czlRegister({color = color, object = switches[color]})
end
check(ours("lines") == 0 and drawn[1] == otherLine and #drawn == 1, "off by default: no trigger lines")
check(switches.White.shown == false, "each switch shows its off state")
local stack = decal("Cactuar stack")
check(stack and stack.url == "https://x/tts/table/stack-panel.png", "the stack panel is always laid on the table")
check(stack and near(stack.position[1], 48.2) and near(stack.position[3], -4.6)
      and near(stack.scale[1], 3.8) and near(stack.scale[2], 22.3), "at the stack column's size")
check(decals[1] == otherDecal and ours("decals") == 1, "other decals stay")

czlToggle({color = "White"})
check(switches.White.memo == "on" and switches.White.shown == true, "clicking turns it on and remembers it")
check(ours("lines") == 1 and drawn[1] == otherLine, "White's trigger area is added; other lines stay")
-- White's mat spans x 14.9..39.7 and z -25.9 (player's edge) to -3.9 (far edge); the
-- library column is at x 41.75, so the box is the far corner on the +x side.
local white = drawn[2].points
check(#white == 3 and at(white[1], 30.28, -3.9) and at(white[2], 30.28, -12.7) and at(white[3], 39.7, -12.7),
      "White's box: down from the far edge, then across to the library side")
check(near(drawn[2].color[1], 0.92) and near(drawn[2].color[3], 0.78), "drawn in White's cream")
local label = decal("Cactuar White triggers")
check(label and label.url == "https://x/tts/table/triggers-White.png", "with White's label")
check(label and near(label.position.x, 34.99) and near(label.position.z, -8.3), "centred in the box")
check(label and label.rotation[1] == 90 and near(label.rotation[2], 0), "flat, reading from White's seat")

czlToggle({color = "Purple"})
local purple = drawn[3].points
-- Purple's mat spans x 19.1..43.9, far edge z 3.9; its library column is at x 17.05.
check(at(purple[1], 28.52, 3.9) and at(purple[2], 28.52, 12.7) and at(purple[3], 19.1, 12.7),
      "a north seat's box is mirrored onto its own library side")
check(near(drawn[3].color[1], 0.627) and near(drawn[3].color[3], 0.941), "drawn in purple")
check(near(decal("Cactuar Purple triggers").rotation[2], 180), "Purple's label reads from its side")
check(ours("lines") == 2 and ours("decals") == 3, "each seat draws its own")

czlToggle({color = "White"})
check(ours("lines") == 1 and switches.White.memo == "off" and switches.White.shown == false,
      "clicking again turns only White's off")
check(decal("Cactuar White triggers") == nil and decal("Cactuar stack") ~= nil, "its label goes; the stack stays")
check(drawn[1] == otherLine and decals[1] == otherDecal, "turning one off never removes other things")

-- A reload (or rewind) keeps the switch memos: the areas come back from them.
CZL = nil
dofile("tts/cactuar_lines.lua")
for _, color in ipairs(CZ.seats) do czlRegister({color = color, object = switches[color]}) end
check(ours("lines") == 1 and ours("decals") == 2 and switches.Purple.shown == true,
      "after a reload Purple's area and the stack are drawn once, not twice")

print(string.format("%d trigger-area checks, %d failed", checks, failures))
os.exit(failures == 0 and 0 or 1)
