-- Async selection, private guides, partner/DFC navigation and shared image assets.
local checks = 0
local function check(value, message) checks = checks + 1; assert(value, message) end
local attrs, assets, requests, payloads = {}, {
  {name = "base", url = "https://example.test/base.png"},
  {name = "czsl_standard", url = "https://example.test/back.jpg"},
  {name = "czsi_1", url = "https://example.test/inspect.webp"}}, {}, {}
UI = {
  getCustomAssets = function() return assets end,
  setAttribute = function(id, key, value) attrs[id] = attrs[id] or {}; attrs[id][key] = value end,
}
JSON = {decode = function(value) return assert(payloads[value], "bad JSON") end}
WebRequest = {get = function(url, callback) requests[#requests + 1] = {url = url, callback = callback} end}
Player = {White = {color = "White", steam_id = "owner-white"}, Red = {color = "Red", steam_id = "owner-red"}}
CZ = {base = "https://example.test/tts/", seats = {"White", "Red"}, state = {}}
local registered = 0
function czSetAssets(value) assets = value; registered = registered + 1 end
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
check(#assets <= 5 and assets[1].name == "base", "commander image registrations are bounded to current open selections")
Player.White.steam_id = "new-owner"
local oldCommander = s.commander
czCommander(white, "next", "cz_commander_next_White")
check(s.commander == oldCommander, "callbacks for an old seat owner are rejected")
print(checks .. " preview checks, 0 failed")
