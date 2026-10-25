-- Battlefield guide lines (tts/cactuar_lines.lua) against stand-ins for Tabletop Simulator.
local checks, failures = 0, 0
local function check(value, message)
  checks = checks + 1
  if not value then failures = failures + 1; print("FAIL: " .. message) end
end
local function near(a, b) return math.abs(a - b) < 0.01 end

CZ = {seats = {"White", "Red", "Yellow", "Green", "Blue", "Purple"}}
-- The real table's playmat zones: south seats face 180, north seats 0.
local mats = {White = {27.3, -14.9, 180}, Red = {-2.1, -14.9, 180}, Yellow = {-31.5, -14.9, 180},
              Green = {-27.3, 14.9, 0}, Blue = {2.1, 14.9, 0}, Purple = {31.5, 14.9, 0}}
data = {}
for color, m in pairs(mats) do
  data[color] = {playmat = {
    getPosition = function() return {x = m[1], y = 1, z = m[2]} end,
    getScale = function() return {x = 24.8, y = 1, z = 22.0} end,
    getRotation = function() return {x = 0, y = m[3], z = 0} end}}
end
-- Vector lines: the edge-strip stack area is already on the table.
local stackLine = {points = {{x = 47, y = 0.97, z = -15}, {x = 49, y = 0.97, z = -15}}, thickness = 0.12}
local drawn = {stackLine}
Global = {getVectorLines = function() return drawn end, setVectorLines = function(lines) drawn = lines end}
Wait = {condition = function(fn, ready) if ready() then fn() end end}
local function switch()
  local s = {memo = "off", shown = nil}
  s.call = function(fn, on) if fn == "czlShow" then s.shown = on end end
  return s
end

dofile("tts/cactuar_lines.lua")
local switches = {}
for _, color in ipairs(CZ.seats) do
  switches[color] = switch()
  czlRegister({color = color, object = switches[color]})
end
local function guides() local n = 0; for _, l in ipairs(drawn) do if near(l.thickness, 0.05) then n = n + 1 end end; return n end
check(guides() == 0 and #drawn == 1, "off by default: only the stack area is drawn")
check(switches.White.shown == false, "each switch shows its off state")

czlToggle({color = "White"})
check(switches.White.memo == "on" and switches.White.shown == true, "clicking turns it on and remembers it")
check(guides() == 1 and drawn[1] == stackLine, "White's divider is added; the stack area stays")
local white = drawn[2].points
-- White's mat spans z -25.9 (player edge) to -3.9: land line at -19.08, divider at -11.49.
check(near(white[1].z, -11.49) and near(white[2].z, -11.49), "divider sits between the land row and the far edge (z " .. white[1].z .. ")")
check(near(math.min(white[1].x, white[2].x), 15.5) and near(math.max(white[1].x, white[2].x), 39.1), "it spans the mat with a small inset")

czlToggle({color = "Purple"})
local purple = drawn[3].points
check(near(purple[1].z, 11.49), "a north seat's divider is mirrored (z " .. purple[1].z .. ")")
check(guides() == 2, "each seat draws its own")

czlToggle({color = "White"})
check(guides() == 1 and switches.White.memo == "off" and switches.White.shown == false, "clicking again turns only White's off")
check(drawn[1] == stackLine, "turning one off never removes other lines")

-- A reload (or rewind) keeps the switch memos: the guides come back from them.
CZL = nil
dofile("tts/cactuar_lines.lua")
drawn = {stackLine, drawn[2]}                         -- the save kept the drawn lines too
for _, color in ipairs(CZ.seats) do czlRegister({color = color, object = switches[color]}) end
check(guides() == 1 and switches.Purple.shown == true, "after a reload Purple's guide is redrawn once, not twice")

print(string.format("%d guide-line checks, %d failed", checks, failures))
os.exit(failures == 0 and 0 or 1)
