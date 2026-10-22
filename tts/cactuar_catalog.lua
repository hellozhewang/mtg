-- Decode the catalog a few small JSON records per frame. TTS's native decoder
-- stalls for seconds on the entire array, even though its HTTP request is async.
function czDecodeCatalog(text, complete, progress, alive)
  local position, index, total, seen, count, finished = 1, nil, nil, {}, 0, false
  local function finish(value, err)
    if finished then return end
    finished = true
    complete(value, err)
  end
  local function line()
    if position > #text then return nil end
    local stop = text:find("\n", position, true) or (#text + 1)
    local value = text:sub(position, stop - 1)
    position = stop + 1
    return value
  end
  local step
  step = function()
    if finished or alive and not alive() then return end
    local started, records = os.clock(), 0
    while records < 2 and os.clock() - started < 0.006 do
      local raw = line()
      if raw == nil then
        if not index or count ~= total then finish(nil, "The deck catalog is incomplete.")
        else finish(index) end
        return
      end
      -- Empty trailing lines are harmless; each published record is small.
      if raw:match("%S") then
        if #raw > 32768 then finish(nil, "A deck catalog record is too large."); return end
        local ok, value = pcall(JSON.decode, raw)
        if not ok or type(value) ~= "table" then finish(nil, "The deck catalog did not read as JSON records."); return end
        if not index then
          if value.v ~= 1 or type(value.count) ~= "number" or value.count < 0 or value.count % 1 ~= 0
            or type(value.tiers) ~= "table" or type(value.themes) ~= "table" or value.decks ~= nil then
            finish(nil, "The deck catalog header is invalid."); return
          end
          index, total = value, value.count
          index.decks = {}
        else
          if type(value.id) ~= "string" or value.id == "" or seen[value.id]
            or type(value.name) ~= "string" or type(value.commander) ~= "string"
            or type(value.owner) ~= "string" or count >= total then
            finish(nil, "The deck catalog contains an invalid deck."); return
          end
          count = count + 1
          index.decks[count], seen[value.id] = value, true
        end
        records = records + 1
      end
    end
    if progress and index then progress(count, total) end
    Wait.frames(step, 1)
  end
  Wait.frames(step, 1)
end
