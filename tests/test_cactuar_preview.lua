-- Async selection, private guides, partner/DFC navigation and shared image assets.
local checks = 0
local function check(value, message) checks = checks + 1; assert(value, message) end
local attrs, assets, requests, payloads = {}, {
  {name = "base", url = "https://example.test/base.png"},
  {name = "czsl_standard", url = "https://example.test/back.jpg"},
  {name = "czsi_1", url = "https://example.test/inspect.webp"}}, {}, {}
UI = {
  getCustomAssets = function() return assets end,
  getAttribute = function(id, key) return attrs[id] and attrs[id][key] end,
  setAttribute = function(id, key, value) attrs[id] = attrs[id] or {}; attrs[id][key] = value end,
}
JSON = {decode = function(value) return assert(payloads[value], "bad JSON") end}
WebRequest = {get = function(url, callback) requests[#requests + 1] = {url = url, callback = callback} end}
Player = {White = {color = "White", steam_id = "owner-white"}, Red = {color = "Red", steam_id = "owner-red"}}
CZ = {base = "https://example.test/tts/", seats = {"White", "Red"}, state = {}}
local registered = 0
local frames, timers = {}, {}
Wait = {frames = function(callback) frames[#frames + 1] = callback end,
        time = function(callback) timers[#timers + 1] = callback end}
local function paint()
  local pending = frames; frames = {}
  for _, callback in ipairs(pending) do callback() end
end
function czSetAssets(value)
  CZ.imageGeneration = (CZ.imageGeneration or 0) + 1
  assets = value; registered = registered + 1
  for color, s in pairs(CZ.state) do if s.open then czRender(color) end end
end
function czRender(color)
  local s = CZ.state[color]
  czpRender(color, s, s.selected)
end
dofile("tts/cactuar_preview.lua")
local function deck(id, guide)
  return {id = id, name = id, commander = id .. " commander", preview = id .. ".preview.json?v=1", guide = guide}
end
local function response(id, commanders, guide)
  return {v = 1, id = id, name = id, commanders = commanders or {
    {name = id, faces = {{name = id, FaceURL = "https://example.test/" .. id .. ".webp"}}}}, guide = guide or {}}
end
local function picture(color)
  paint()
  for _, asset in ipairs(assets) do if asset.name == attrs["cz_commander_image_" .. color].image then return asset.url end end
end
local a, b = deck("a", true), deck("b", true)
CZ.state.White = {player = "owner-white", open = true, selected = a}
local white, red, s = Player.White, Player.Red, CZ.state.White
czRender("White")
check(#requests == 1 and attrs.cz_commander_note_White.active == "True", "selection fetches a small preview with loading feedback")
czRender("White")
check(#requests == 1, "rendering while pending never duplicates a request")
czGuide(white, nil, "cz_guide_White")
check(s.guideOpen and attrs.cz_guide_text_White.text == "Loading guide…", "guide can open while metadata is pending")
s.selected = b; czRender("White")
check(#requests == 2 and not s.guideOpen, "a new selection resets guide and commander navigation")
payloads.a = response("a")
requests[1].callback({text = "a"})
check(attrs.cz_commander_image_White.image == "", "a late response cannot show the previous commander's image")
payloads.b = response("b", nil, {{title = "Plan <x>", rows = {
  {name = "Card <i> + Other", text = "Read & play. " .. string.rep("Long readable prose. ", 180)}}}})
requests[2].callback({text = "b"})
check(attrs.cz_commander_image_White.image == "" and #frames > 0, "image binding waits for a later renderer frame")
check(picture("White") == "https://example.test/b.webp", "the current commander's exact face is a named image asset")
check(assets[1].name == "base" and assets[2].name == "czsl_standard" and assets[3].name == "czsi_1", "base, sleeve and Inspect images survive registration")
local previousRegistered = registered
czRender("White")
check(registered == previousRegistered, "unchanged selections do not reload UI assets")
czGuide(white, nil, "cz_guide_White")
check(attrs.cz_guide_view_White.active == "True" and attrs.cz_deck_list_White.active == "False", "Guide replaces the list while the commander stays visible")
check(attrs.cz_guide_text_White.text:find("Plan ‹x›", 1, true) and not attrs.cz_guide_text_White.text:find("<i>", 1, true), "guide content cannot inject rich-text tags")
check(tonumber(attrs.cz_guide_text_White.height) > 1000, "long guides have scrollable content height")
czGuideClose(red, nil, "cz_guide_back_White")
check(s.guideOpen, "another player cannot close the private guide")
czGuideClose(white, nil, "cz_guide_back_White")
check(not s.guideOpen and attrs.cz_deck_list_White.active == "True", "Back preserves selection and restores the deck list")

local pair = deck("pair", false)
s.selected = pair; czRender("White")
payloads.pair = response("pair", {
  {name = "First", faces = {{name = "First", FaceURL = "https://example.test/first.webp"}}},
  {name = "Second", faces = {{name = "Second", FaceURL = "https://example.test/second.webp"},
    {name = "Back", FaceURL = "https://example.test/back.webp"}}}})
requests[3].callback({text = "pair"})
check(picture("White") == "https://example.test/first.webp", "partner previews start with the first commander")
czCommander(white, "next", "cz_commander_next_White")
check(picture("White") == "https://example.test/second.webp" and s.commander == 2, "Next shows the second commander at full size")
czCommander(red, "prev", "cz_commander_prev_White")
check(s.commander == 2, "another player cannot switch a private preview")
czCommander(white, "flip", "cz_commander_flip_White")
check(picture("White") == "https://example.test/back.webp", "a double-faced commander can show its pinned back face")
czCommander(white, "prev", "cz_commander_prev_White")
check(s.commander == 1 and s.commanderFace == 1, "switching commanders resets to its front face")
check(attrs.cz_guide_White.interactable == "False", "a deck without a guide does not offer an empty guide")
czGuide(white)
check(not s.guideOpen, "a forged guide click cannot open an unavailable guide")

CZ.state.Red = {player = "owner-red", open = true, selected = b}
czRender("Red")
check(picture("Red") == "https://example.test/b.webp" and picture("White") == "https://example.test/first.webp", "simultaneous players keep different commander previews")
local count = #requests
czRender("Red")
check(#requests == count, "metadata cache is reused across seats")
s.selected = deck("broken", true); czRender("White")
requests[#requests].callback({is_error = true})
check(attrs.cz_commander_note_White.text:find("Press Refresh", 1, true), "network failure explains how to retry")
czpRefresh(); czRender("White")
check(#requests == count + 2, "Refresh permits retry after a failed preview request")
payloads.wrong = response("wrong-deck")
requests[#requests].callback({text = "wrong"})
check(CZ.previews[s.selected.preview].status == "error", "a mismatched payload cannot impersonate the selected deck")
s.selected = a; czRender("White")
check(#assets <= CZ.previewLimit + 3 and assets[1].name == "base", "recent commander pictures stay within the cache bound")
s.open = false; paint()
check(attrs.cz_commander_image_White.image == "", "a pending image cannot repaint a closed browser")
s.open = true; czRender("White")
UI.loading = true; paint()
check(attrs.cz_commander_image_White.image == "", "a pending image cannot bind during a shared UI reload")
UI.loading = false; czRender("White")
check(picture("White") == "https://example.test/a.webp", "the post-reload render restores the commander image")
local pending = timers; timers = {}
for _, callback in ipairs(pending) do callback() end
check(picture("White") == "https://example.test/a.webp", "late sprite retries cannot restore an earlier selection")
Player.White.steam_id = "new-owner"
czRender("White"); paint()
check(attrs.cz_commander_image_White.image == "", "a pending image cannot repaint for a new seat owner")
local oldCommander = s.commander
czCommander(white, "next", "cz_commander_next_White")
check(s.commander == oldCommander, "callbacks for an old seat owner are rejected")
-- Render the actual website-style XML module, not the text-only compatibility path.
Player.White.steam_id = "owner-white"
local baseXml = string.rep('<Panel><Text text="Other module UI"/></Panel>', 2000)
local otherGuide = '<VerticalLayout id="cz_guide_content_Red"><Text text="Private Red guide"/></VerticalLayout>'
local xml = baseXml .. '<VerticalLayout id="cz_guide_content_White"><Text/></VerticalLayout>' .. otherGuide
UI.getXml = function() return xml end
function czGuideXml(value)
  CZ.imageGeneration = (CZ.imageGeneration or 0) + 1
  xml = value
  for color, state in pairs(CZ.state) do if state.open then czRender(color) end end
end
dofile("tts/cactuar_guide.lua")
local function card(name, joiner)
  return {name = name, joiner = joiner or "", faces = {{name = name, FaceURL = "https://example.test/" .. name .. ".webp"}}}
end
s.selected = deck("illustrated", true); czRender("White")
payloads.illustrated = response("illustrated", nil, {{title = "Plan & <win>", rows = {
  {name = "First", text = "A card beside prose.", cards = {card("First")}},
  {name = "First -> Second + Third", text = "A chain of pictures above prose.", cards = {
    card("First"), card("Second", "->"), card("Third", "+")}},
  {name = "", text = "Ordinary prose remains readable.", cards = {}}}}})
requests[#requests].callback({text = "illustrated"})
czGuide(white, nil, "cz_guide_White"); paint()
check(xml:find('cz_guide_pic_4_White', 1, true) and xml:find('A card beside prose.', 1, true), "single-card and combo rows include every picture and their prose")
check(xml:find('Plan &amp; ‹win›', 1, true) and xml:find('→', 1, true), "headings are escaped and chains retain their direction")
check(xml:sub(1, #baseXml) == baseXml and xml:sub(-#otherGuide) == otherGuide, "guide replacement preserves the large base UI and other private guides exactly")
check(assets[1].name == "base" and assets[2].name == "czsl_standard" and assets[3].name == "czsi_1", "illustrated guides preserve every other module's image assets")
local previousXml, commander = xml, s.commander
czGuideHover(white, nil, "cz_guide_pic_3_White")
check(picture("White") == "https://example.test/Second.webp" and xml == previousXml, "hover previews the right combo piece without rebuilding the guide")
czGuideHover(red, nil, "cz_guide_pic_2_White")
check(s.guideHover.name == "Second", "another seat cannot change a guide preview")
czGuideUnhover(white, nil, "cz_guide_pic_2_White")
check(s.guideHover.name == "Second", "late exits from another picture cannot dismiss the current preview")
czGuideUnhover(white, nil, "cz_guide_pic_3_White")
check(picture("White") == "https://example.test/illustrated.webp" and s.commander == commander, "leaving a guide picture restores the commander and partner position")
czGuideClose(white, nil, "cz_guide_back_White")
check(not s.guideHover and not s.guideOpen and #assets <= CZ.previewLimit + 3, "closing a guide preserves bounded cached pictures")

-- Modern catalogs carry only commander faces; the pictured guide is requested
-- on demand. Repeated selection/hover must not blank a bound image or reload UI.
local modern = deck("modern", true)
modern.commanders = response("modern").commanders
count = #requests
s.selected = modern; czRender("White")
check(#requests == count and picture("White") == "https://example.test/modern.webp", "catalog commander renders without fetching the full illustrated guide")
local loadedImage = attrs.cz_commander_image_White.image
local rendered, timed = registered, #timers
czRender("White")
check(attrs.cz_commander_image_White.image == loadedImage and #timers == timed, "unchanged commander stays painted without scheduling another clear/rebind")
CZ.imageGeneration = (CZ.imageGeneration or 0) + 1
czRender("White")
check(attrs.cz_commander_image_White.image == "" and picture("White") == "https://example.test/modern.webp", "a shared UI reload rebinds the cached sprite even when its image attribute survived")
s.selected = a; czRender("White"); paint()
s.selected = modern; czRender("White"); paint()
check(registered == rendered and #requests == count, "returning to cached commanders causes no metadata request or shared asset reload")
czGuide(white, nil, "cz_guide_White")
check(#requests == count + 1 and xml:find("Loading guide…", 1, true), "only opening Read guide requests its content and shows loading feedback")
czRender("White")
check(#requests == count + 1, "guide redraws do not duplicate its pending request")
czGuideClose(white, nil, "cz_guide_back_White")
payloads.modern = response("modern", nil, {{title = "Lazy guide", rows = {
  {name = "Lazy", text = "Only download on Read guide.", cards = {card("Lazy")}}}}})
requests[#requests].callback({text = "modern"})
check(not s.guideOpen and attrs.cz_guide_view_White.active == "False", "a late guide response cannot reopen the closed reading view")
czGuide(white, nil, "cz_guide_White"); paint()
check(#requests == count + 1 and xml:find("Only download on Read guide.", 1, true), "reopening uses the cached illustrated guide")
rendered = registered
czGuideClose(white, nil, "cz_guide_back_White")
check(registered == rendered, "closing the guide never reloads shared image assets")

local failing = deck("lazy-failure", true)
failing.commanders = response("lazy-failure").commanders
s.selected = failing; czRender("White"); paint()
czGuide(white, nil, "cz_guide_White")
requests[#requests].callback({is_error = true})
check(picture("White") == "https://example.test/lazy-failure.webp" and xml:find("Could not load the guide", 1, true), "guide failure leaves the commander usable with a separate retry message")
count = #requests
czpRefresh(); czRender("White")
check(#requests == count + 1, "Refresh retries a failed lazy guide without refetching commander metadata")
czGuideClose(white, nil, "cz_guide_back_White")

local limit = CZ.previewLimit
CZ.previewLimit = 4
for i = 1, 10 do
  local d = deck("cached-" .. i, false)
  d.commanders = response("cached-" .. i).commanders
  s.selected = d; czRender("White"); paint()
end
check(#assets <= CZ.previewLimit + 3, "eviction bounds retained images while preserving base/sleeve/Inspect assets")
check(picture("Red") == "https://example.test/b.webp", "eviction keeps another seat's active commander registered")
CZ.previewLimit = limit
print(checks .. " preview checks, 0 failed")
