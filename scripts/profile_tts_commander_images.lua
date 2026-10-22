-- Temporary live A/B benchmark. Driven by profile_tts_commander_images.py.
-- No production handlers, cards, turns, hotkeys or released saves are changed.
local b = CZPB
local browser, state, owner = CZ, CZ.state.White, Player.White.steam_id
local selected = state.selected
local baselineAssets = UI.getCustomAssets()
b.results, b.calls, b.frames = {}, {}, {}
b.phase, b.running, b.ready = "warming_text", true, false
local expected = selected
local function current()
  return CZPB == b and CZ == browser and CZ.state.White == state and Player.White.steam_id == owner
end
local function redraw()
  CZ.imageGeneration = (CZ.imageGeneration or 0) + 1
  for _, c in ipairs(CZ.seats) do
    local s = CZ.state[c]
    if s and s.open then czRender(c) end
  end
  if czsRedrawOpen then czsRedrawOpen() end
end
local function settle(done)
  Wait.frames(function()
    Wait.condition(function()
      Wait.frames(function()
        if UI.loading then settle(done) else done() end
      end, 2)
    end, function() return not UI.loading end, 30, function()
      b.error, b.running, b.phase = "UI asset loading timed out", false, "error"
    end)
  end, 1)
end
local function stats(values)
  local out = {n = #values, mean_ms = 0, p50_ms = 0, p95_ms = 0, p99_ms = 0, max_ms = 0,
    over16 = 0, over33 = 0, over50 = 0, over100 = 0}
  if #values == 0 then return out end
  local sorted, sum = {}, 0
  for i,v in ipairs(values) do
    sorted[i], sum = v, sum + v
    if v > 0.016667 then out.over16 = out.over16 + 1 end
    if v > 0.033333 then out.over33 = out.over33 + 1 end
    if v > 0.05 then out.over50 = out.over50 + 1 end
    if v > 0.1 then out.over100 = out.over100 + 1 end
  end
  table.sort(sorted)
  out.mean_ms = sum / #values * 1000
  out.p50_ms = sorted[math.max(1,math.ceil(#values * 0.5))] * 1000
  out.p95_ms = sorted[math.max(1,math.ceil(#values * 0.95))] * 1000
  out.p99_ms = sorted[math.max(1,math.ceil(#values * 0.99))] * 1000
  out.max_ms = sorted[#sorted] * 1000
  return out
end
local monitoring, monitorWait = false, nil
local function monitor()
  if not monitoring or not current() then return end
  local now = os.clock()
  if b.lastClock then
    local gap = now-b.lastClock
    b.gaps[#b.gaps+1] = gap
    if not b.largestGap or gap>b.largestGap.clock_seconds then
      b.largestGap={clock_seconds=gap,frame_steps=Time.frame_count-b.lastFrame,
        reported_delta_time=Time.delta_time,game_seconds=Time.time-b.lastGame}
    end
  end
  b.lastClock,b.lastFrame,b.lastGame = now,Time.frame_count,Time.time
  b.frames[#b.frames+1] = Time.delta_time
  monitorWait = Wait.frames(monitor, 1)
end
local function stopSample()
  monitoring = false
  if monitorWait then Wait.stop(monitorWait); monitorWait = nil end
end
local function sample(label, action, done)
  if not current() then b.error="Browser/owner changed";b.running=false;return end
  if state.selected ~= expected then b.error="Selection changed during benchmark";b.running=false;return end
  b.phase, b.frames, b.gaps, b.lastClock, b.calls, b.largestGap = label, {}, {}, nil, {}, nil
  local startClock, startTime = os.clock(), Time.time
  local record = {label=label, assets_before=#UI.getCustomAssets()}
  b.results[#b.results+1] = record
  monitoring = true;monitor()
  local function finish()
    stopSample()
    if not current() or not b.running then return end
    record.elapsed_game_ms, record.elapsed_clock_ms = (Time.time-startTime)*1000, (os.clock()-startClock)*1000
    record.frames, record.clock_gaps, record.calls = stats(b.frames), stats(b.gaps), stats(b.calls)
    record.assets_after = #UI.getCustomAssets()
    record.largest_gap_detail = b.largestGap
    -- Stats/sorting/coordinator work falls outside the following sample.
    Wait.frames(done, 12)
  end
  local function measured(fn)
    local t=os.clock();fn();b.calls[#b.calls+1]=os.clock()-t
  end
  action(measured, finish, record)
end
local function delay(done, seconds) Wait.time(done, seconds or 1.5) end
local function paint(name)
  UI.setAttribute("czpbench_image_White", "image", name or "")
  UI.setAttribute("czpbench_image_White", "color", name and "#FFFFFF" or "#FFFFFF00")
  UI.setAttribute("czpbench_panel_White", "active", name and "True" or "False")
end
local function select(i)
  state.selected = b.decks[i];expected = state.selected;czRender("White")
end
local function cycle(pictures, reopen)
  return function(measured, finish)
    local i = 0
    local function nextOne()
      if not current() or not b.running then return end
      i=i+1
      if i>18 then delay(finish,0.25);return end
      local n=(i-1)%#b.decks+1
      measured(function()
        if reopen then
          state.open=false;UI.setAttribute("cz_panel_White","active","False");paint(nil)
        end
        select(n)
        state.open=true;UI.setAttribute("cz_panel_White","active","True");czRender("White")
        paint(pictures and b.names[n] or nil)
      end)
      delay(nextOne,0.18)
    end
    nextOne()
  end
end
local tasks={}
local function add(label,fn) tasks[#tasks+1]={label,fn} end
local function noop(_,finish) delay(finish,2) end
add("text_only_idle",noop)
add("text_only_switch",cycle(false,false))
add("text_only_reopen",cycle(false,true))
-- The initial six empty image controls are a one-time harness layout operation.
-- A production build would declare them in its original XML instead.
add("harness_layout_setup",function(measured,finish,record)
  measured(function() UI.setXml(b.testXml) end)
  settle(function() redraw();record.ready_clock_ms=(os.clock()-b.layoutStart)*1000;delay(finish,0.5) end)
end)
add("empty_image_controls_idle",noop)
for i=1,3 do
  local trial=i
  add("unchanged_assets_rebuild_"..trial,function(measured,finish,record)
    local started=os.clock()
    measured(function() UI.setCustomAssets(UI.getCustomAssets()) end)
    settle(function() record.ready_clock_ms=(os.clock()-started)*1000;redraw();delay(finish,0.75) end)
  end)
end
b.names={}
for i=1,#b.decks do
  local n=i
  b.names[n]="czpbench_normal_"..n
  add("first_registration_"..n,function(measured,finish,record)
    select(n);paint(nil)
    local merged=UI.getCustomAssets()
    merged[#merged+1]={name=b.names[n],url=b.urls[n]}
    local started=os.clock()
    measured(function() UI.setCustomAssets(merged) end)
    settle(function()
      record.ready_clock_ms=(os.clock()-started)*1000;redraw();paint(b.names[n]);delay(finish,1)
    end)
  end)
end
for i=1,#b.decks do
  local n=i
  add("fresh_url_registration_"..n,function(measured,finish,record)
    select(n);paint(nil)
    local name="czpbench_fresh_"..n
    local merged=UI.getCustomAssets()
    merged[#merged+1]={name=name,url=b.freshUrls[n]}
    local started=os.clock()
    measured(function() UI.setCustomAssets(merged) end)
    settle(function()
      record.ready_clock_ms=(os.clock()-started)*1000;redraw();paint(name);delay(finish,1)
    end)
  end)
end
add("cached_image_idle",function(_,finish) paint(b.names[1]);delay(finish,2) end)
add("cached_image_switch",cycle(true,false))
add("cached_image_reopen",cycle(true,true))
add("cached_image_switch_repeat",cycle(true,false))
add("text_only_switch_repeat",cycle(false,false))
add("text_only_idle_repeat",function(_,finish) paint(nil);delay(finish,2) end)
function b.cleanup()
  stopSample();b.running=false;b.phase="cleaning_up"
  -- Remove only our temporary asset names; retain any unrelated additions.
  local assets={}
  for _,a in ipairs(UI.getCustomAssets()) do
    if not a.name:match("^czpbench_") then assets[#assets+1]=a end
  end
  if current() then state.selected=selected;state.open=b.wasOpen end
  UI.setXml(b.originalXml,assets)
  settle(function() redraw();b.phase="restored";b.restored=true;b.assets_after_cleanup=#UI.getCustomAssets() end)
end
local position=0
local function nextTask()
  if not b.running then return end
  if not current() or b.error then b.running=false;b.phase="error";return end
  position=position+1
  local task=tasks[position]
  if not task then
    b.running=false;b.phase="visual_check";select(1);paint(b.names[1]);return
  end
  if task[1]=="harness_layout_setup" then b.layoutStart=os.clock() end
  sample(task[1],task[2],nextTask)
end
-- Warm only commander text (not guides/images) so image costs are not conflated
-- with network/text parsing. The original selection is restored at cleanup.
local warm=0
local function warmNext()
  if not current() then b.error="Browser/owner changed";b.running=false;return end
  warm=warm+1
  if warm>#b.decks then
    select(1);b.ready=true;Wait.frames(nextTask,60);return
  end
  select(warm)
  Wait.condition(warmNext,function()
    local e=CZ.commanderTexts[b.decks[warm].commander_text]
    return e and e.status~="loading"
  end,15,function() b.error="Commander text warmup timed out";b.running=false end)
end
warmNext()
