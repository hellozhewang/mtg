-- Plays tts/cactuar.lua against stand-ins for Tabletop Simulator's API and the
-- real files build_site.py writes under docs/tts/. Run from the repo root:
--     lua tests/test_cactuar.lua
-- tests/test_cactuar_lua.py runs it as part of the suite when lua is installed.

local failures, checks = 0, 0
local function check(cond, what)
  checks = checks + 1
  if not cond then
    failures = failures + 1
    print("FAIL: " .. what)
  end
end

-- ---------- a small JSON decoder (Tabletop Simulator provides JSON.decode) ----------
local function decode(s)
  local i = 1
  local function ws() i = s:find("[^ \t\r\n]", i) or #s + 1 end
  local value
  local function str()
    local out, j = {}, i + 1
    while true do
      local c = s:sub(j, j)
      if c == '"' then i = j + 1; return table.concat(out) end
      if c == "\\" then
        local e = s:sub(j + 1, j + 1)
        local map = {n = "\n", t = "\t", r = "\r", b = "\b", f = "\f", ['"'] = '"', ["\\"] = "\\", ["/"] = "/"}
        if e == "u" then
          out[#out + 1] = utf8.char(tonumber(s:sub(j + 2, j + 5), 16)); j = j + 6
        else
          out[#out + 1] = map[e]; j = j + 2
        end
      else
        out[#out + 1] = c; j = j + 1
      end
    end
  end
  function value()
    ws()
    local c = s:sub(i, i)
    if c == "{" then
      local t = {}; i = i + 1; ws()
      if s:sub(i, i) == "}" then i = i + 1; return t end
      while true do
        ws(); local k = str(); ws(); i = i + 1
        t[k] = value(); ws()
        local d = s:sub(i, i); i = i + 1
        if d == "}" then return t end
      end
    elseif c == "[" then
      local t = {}; i = i + 1; ws()
      if s:sub(i, i) == "]" then i = i + 1; return t end
      while true do
        t[#t + 1] = value(); ws()
        local d = s:sub(i, i); i = i + 1
        if d == "]" then return t end
      end
    elseif c == '"' then return str()
    elseif s:sub(i, i + 3) == "true" then i = i + 4; return true
    elseif s:sub(i, i + 4) == "false" then i = i + 5; return false
    elseif s:sub(i, i + 3) == "null" then i = i + 4; return nil
    else
      local num = s:match("^-?%d+%.?%d*[eE]?[-+]?%d*", i)
      i = i + #num
      return math.tointeger(tonumber(num)) or tonumber(num)
    end
  end
  return value()
end
JSON = {decode = decode}

local function read(path)
  local f = assert(io.open(path, "rb"))
  local text = f:read("a"); f:close()
  return text
end

-- ---------- stand-ins for the Tabletop Simulator API ----------
-- Tabletop Simulator ignores UI.setValue on a <Button>: its label is the "text"
-- attribute. So setValue on any Button id in tts/cactuar.xml is a failure.
local buttons = {}
for id in read("tts/cactuar.xml"):gmatch('<Button id="([^"]+)"') do
  buttons[#buttons + 1] = "^" .. id:gsub("{C}", "%%a+"):gsub("{I}", "%%d+") .. "$"
end
check(#buttons >= 9, "the stub knows the Buttons (" .. #buttons .. ")")
local function isButton(id)
  for _, pattern in ipairs(buttons) do
    if id:match(pattern) then return true end
  end
  return false
end
local attrs, values = {}, {}
UI = {
  setValue = function(id, v)
    check(not isButton(id), "setValue on Button " .. id .. ": label it with setAttribute text")
    values[id] = v
  end,
  setAttribute = function(id, k, v) attrs[id] = attrs[id] or {}; attrs[id][k] = v end,
  getAttribute = function(id, k) return (attrs[id] or {})[k] end,
}
local requests = 0
WebRequest = {get = function(url, cb)
  requests = requests + 1
  local path = "docs/tts/" .. url:gsub("^test://tts/", ""):gsub("%?.*$", "")
  local ok, text = pcall(read, path)
  cb({is_error = not ok, error = ok and nil or "404", text = ok and text or ""})
end}
local spawned, broadcasts, shuffled = {}, {}, 0
function spawnObjectJSON(p)
  spawned[#spawned + 1] = p
  if p.callback_function then p.callback_function({shuffle = function() shuffled = shuffled + 1 end}) end
end
function broadcastToAll(msg) broadcasts[#broadcasts + 1] = msg end
function broadcastToColor(msg, color) broadcasts[#broadcasts + 1] = color .. ": " .. msg end
local function obj(name, x, z)
  return {getName = function() return name end, getPosition = function() return {x = x, y = 1, z = z} end}
end
function getAllObjects()       -- White's two Commander Zones, and another seat's
  return {obj("Commander Zone", 41.8, -9.6), obj("Commander Zone", 41.8, -13.4),
          obj("Commander Zone", 12.4, -13.4), obj("Life Tracker", 41.8, -12)}
end
local inZone = {}
data = {White = {libraryZone = {
  getPosition = function() return {x = 41.8, y = 2.46, z = -20.1} end,
  getRotation = function() return {x = 0, y = 0, z = 0} end,
  getTransformForward = function() return {x = 0, y = 0, z = 1} end,
  getObjects = function() return inZone end,
}}}

-- ---------- load the browser ----------
local source = read("tts/cactuar.lua"):gsub("@BASE_URL@", "test://tts/")
assert(load(source, "cactuar.lua"))()
local white, grey = {color = "White", steam_name = "zz"}, {color = "Grey", steam_name = "spectator"}

-- A spectator cannot open it: decks load into your own seat.
czOpenFor({color = "Grey"})
check(broadcasts[1] and broadcasts[1]:find("Take a seat"), "spectator is told to sit")
check(attrs["cz_panel_Grey"] == nil, "no panel for a spectator")

-- Clicking a Cactuar tile fetches the index and fills the rows, strongest tier first.
czOpenFor({color = "White"})
check(attrs["cz_panel_White"].active == "True", "panel opens")
check(CZ.index and #CZ.index.decks > 100, "index loaded")
local s = CZ.state.White
check(#s.list == #CZ.index.decks, "every deck listed")
check(s.list[1].tier == "GOD", "tier sort puts GOD first (got " .. tostring(s.list[1].tier) .. ")")
check(attrs["cz_row_1_White"].text:find(s.list[1].name, 1, true), "row 1 shows the first deck")
check(attrs["cz_row_12_White"].active == "True", "a full first page")
check(values["cz_page_White"]:find("^Page 1 /"), "pager text")

-- Sorting by name, then filtering by owner.
czSort(white, "name")
for k = 2, #s.list do
  check(s.list[k - 1].name:lower() <= s.list[k].name:lower(), "name order at " .. k)
end
czCycle(white, "owner")
local owner = s.filter.owner
check(owner == "digitalstealth", "first owner alphabetically (got " .. tostring(owner) .. ")")
for _, d in ipairs(s.list) do check(d.owner == owner, "owner filter keeps only " .. owner) end
check(attrs["cz_f_owner_White"].text == owner, "owner button shows the value")
czClear(white)
check(next(s.filter) == nil and #s.list == #CZ.index.decks, "Clear resets filters")

-- Search, pick, load: Giada lands in White's seat.
czSearch(white, "giada")
check(#s.list >= 1 and s.list[1].name == "Giada-Angels", "search finds Giada")
czPick(white, "1")
check(s.selected and s.selected.name == "Giada-Angels", "picked Giada")
check(values["cz_detail_White"]:find("Giada, Font of Hope", 1, true), "detail shows the commander")
czLoad(white)
check(#spawned == 3, "library, commander and tokens spawn (got " .. #spawned .. ")")
local library, commander, tokens = spawned[1], spawned[2], spawned[3]
check(library.position[1] == 41.8 and library.position[3] == -20.1, "library in the library zone")
check(library.rotation[3] == 180 and library.rotation[2] == 180, "library face down, facing the seat")
check(shuffled == 1, "library shuffled")
check(decode(library.json).Name == "DeckCustom" and #decode(library.json).ContainedObjects == 99, "99-card library")
check(commander.position[3] == -13.4 and commander.rotation[3] == 0, "commander face up on the nearer Commander Zone")
check(decode(commander.json).Nickname:find("^Giada, Font of Hope"), "the commander is Giada")
check(tokens.position[3] > -13.4, "tokens beyond the Commander Zones")
check(broadcasts[#broadcasts]:find("zz loaded Giada%-Angels"), "the table is told")
check(attrs["cz_panel_White"].active == "False", "panel closes after loading")

-- The tile toggles: a second click closes an open panel.
czOpenFor({color = "White"})
check(attrs["cz_panel_White"].active == "True", "tile opens the panel")
czOpenFor({color = "White"})
check(attrs["cz_panel_White"].active == "False", "a second click closes it")

-- A partner pair takes both Commander Zones.
spawned = {}
czOpen(white); czSearch(white, "akroma"); czPick(white, "1"); czLoad(white)
check(#spawned >= 3, "partner deck spawns library and two commanders")
check(spawned[2].position[3] == -13.4 and spawned[3].position[3] == -9.6, "one commander per Commander Zone")
check(decode(spawned[3].json).Nickname:find("^Vial Smasher"), "the partner is Vial Smasher")

-- A library zone that already holds a deck is left alone.
spawned, inZone = {}, {{type = "Deck"}}
czOpen(white); czLoad(white)
check(#spawned == 0, "no spawn onto an existing deck")
check(values["cz_status_White"]:find("not empty"), "and the player is told why")

print(string.format("%d checks, %d failed", checks, failures))
os.exit(failures == 0 and 0 or 1)
