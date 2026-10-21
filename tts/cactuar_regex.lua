-- Boolean regex search for Workshop Lua. Thompson NFA: no backtracking or eval.
-- Supports groups, alternation, classes, anchors, word boundaries and repetitions.
-- Anchors match line boundaries; dot excludes newlines. Captures are not returned.
CZRegex = {}
do
  local function chars(text)
    local out = {}
    for c in text:gmatch("[%z\1-\127\194-\244][\128-\191]*") do out[#out + 1] = c end
    return out
  end
  local function word(c) return c ~= nil and c:match("^[%w_]$") ~= nil end
  local function classMatch(test, c)
    if not c then return false end
    if test.kind == "literal" then return c == test.value end
    if test.kind == "dot" then return c ~= "\n" and c ~= "\r" end
    if test.kind == "range" then return c >= test.first and c <= test.last end
    if test.kind == "builtin" then
      local hit = test.value == "d" and c:match("^%d$") ~= nil
        or test.value == "w" and word(c)
        or test.value == "s" and c:match("^%s$") ~= nil
      return test.negate and not hit or not test.negate and hit
    end
    local hit = false
    for _, item in ipairs(test.items) do if classMatch(item, c) then hit = true; break end end
    return test.negate and not hit or not test.negate and hit
  end

  function CZRegex.compile(pattern, fold)
    fold = fold or string.lower
    local ok, result = pcall(function()
      if #pattern > 256 then error("Regex is too long (maximum 256 bytes).", 0) end
      local input, at, depth = chars(pattern), 1, 0
      local function peek() return input[at] end
      local function pop() local c = peek(); at = at + 1; return c end
      local function fail(message) error(message .. " (near character " .. at .. ").", 0) end
      local function literal(c) return {kind = "literal", value = fold(c)} end
      local function escape(inClass)
        local c = pop()
        if not c then fail("Incomplete escape") end
        if c:match("^[dDwWsS]$") then
          return {kind = "builtin", value = c:lower(), negate = c ~= c:lower()}
        end
        if not inClass and (c == "b" or c == "B") then return {kind = "boundary", negate = c == "B"} end
        local escaped = {n = "\n", r = "\r", t = "\t", f = "\f", v = "\v"}
        if escaped[c] then return literal(escaped[c]) end
        if c:match("^[%w]$") then fail("Unsupported escape \\" .. c) end
        return literal(c)
      end
      local function characterClass()
        local items, negate = {}, false
        if peek() == "^" then negate = true; pop() end
        local function item()
          local c = pop()
          if c == "\\" then return escape(true) end
          return literal(c)
        end
        while peek() and peek() ~= "]" do
          local first = item()
          if peek() == "-" and input[at + 1] and input[at + 1] ~= "]" then
            pop()
            local last = item()
            if first.kind ~= "literal" or last.kind ~= "literal" or #chars(first.value) ~= 1
                or #chars(last.value) ~= 1 or first.value > last.value then fail("Invalid character range") end
            items[#items + 1] = {kind = "range", first = first.value, last = last.value}
          else
            if first.kind == "literal" and #chars(first.value) ~= 1 then fail("Character class requires single characters") end
            items[#items + 1] = first
          end
        end
        if not peek() then fail("Unclosed character class") end
        pop()
        if #items == 0 then fail("Empty character class") end
        return {kind = "class", items = items, negate = negate}
      end
      local expression
      local function atom()
        local c = pop()
        if c == "(" then
          depth = depth + 1
          if depth > 24 then fail("Groups are nested too deeply") end
          if peek() == "?" then
            pop()
            if pop() ~= ":" then fail("Only ordinary groups and (?:...) are supported") end
          end
          local node = expression()
          if pop() ~= ")" then fail("Unclosed group") end
          depth = depth - 1
          return node
        elseif c == "[" then return characterClass()
        elseif c == "\\" then return escape(false)
        elseif c == "." then return {kind = "dot"}
        elseif c == "^" then return {kind = "start"}
        elseif c == "$" then return {kind = "finish"}
        elseif c:match("^[*+?{}%]]$") then fail("Unexpected " .. c)
        else return literal(c) end
      end
      local function repetition()
        local node, c = atom(), peek()
        local low, high
        if c == "*" then low = 0; pop()
        elseif c == "+" then low = 1; pop()
        elseif c == "?" then low, high = 0, 1; pop()
        elseif c == "{" then
          pop()
          local function number()
            local digits = ""
            while peek() and peek():match("^%d$") do digits = digits .. pop() end
            return tonumber(digits)
          end
          low = number()
          if not low then fail("Expected a repeat count") end
          high = low
          if peek() == "," then pop(); high = number() end
          if pop() ~= "}" then fail("Unclosed repeat count") end
          if low > 64 or high and high > 64 then fail("Repeat count exceeds 64") end
          if high and high < low then fail("Invalid repeat range") end
        end
        if low then
          if node.kind == "start" or node.kind == "finish" or node.kind == "boundary" then fail("Cannot repeat an anchor") end
          -- Greediness cannot change a boolean search result.
          if peek() == "?" then pop() end
          node = {kind = "repeat", child = node, low = low, high = high}
        end
        return node
      end
      local function sequence()
        local items = {}
        while peek() and peek() ~= "|" and peek() ~= ")" do items[#items + 1] = repetition() end
        return {kind = "sequence", items = items}
      end
      expression = function()
        local items = {sequence()}
        while peek() == "|" do pop(); items[#items + 1] = sequence() end
        return {kind = "alternation", items = items}
      end
      local ast = expression()
      if peek() then fail("Unexpected " .. peek()) end
      -- Skip impossible starting characters without allocating NFA work lists.
      -- This matters in MoonSharp when scanning every description in a library.
      local first
      local function union(a, b)
        if not a or not b then return nil end
        for c in pairs(b) do a[c] = true end
        return a
      end
      first = function(node)
        if node.kind == "literal" then
          local c = chars(node.value)[1]
          return c and {[c] = true} or {}, c == nil
        elseif node.kind == "sequence" then
          local starts, empty = {}, true
          for _, child in ipairs(node.items) do
            local candidates, nullable = first(child)
            starts = union(starts, candidates)
            if not nullable then empty = false; break end
          end
          return starts, empty
        elseif node.kind == "alternation" then
          local starts, empty = {}, false
          for _, child in ipairs(node.items) do
            local candidates, nullable = first(child)
            starts, empty = union(starts, candidates), empty or nullable
          end
          return starts, empty
        elseif node.kind == "repeat" then
          local starts, nullable = first(node.child)
          return starts, node.low == 0 or nullable
        elseif node.kind == "start" or node.kind == "finish" or node.kind == "boundary" then return {}, true
        else return nil, false end
      end
      local starts, nullable = first(ast)
      if nullable then starts = nil end
      local states = {}
      local function state(node)
        if #states >= 512 then fail("Regex expands to too many states; simplify it") end
        states[#states + 1] = node
        return #states
      end
      local emit
      emit = function(node, nextState)
        if node.kind == "sequence" then
          for i = #node.items, 1, -1 do nextState = emit(node.items[i], nextState) end
          return nextState
        elseif node.kind == "alternation" then
          local branch = emit(node.items[#node.items], nextState)
          for i = #node.items - 1, 1, -1 do branch = state({kind = "split", out = emit(node.items[i], nextState), other = branch}) end
          return branch
        elseif node.kind == "repeat" then
          if not node.high then
            local loop = state({kind = "split", other = nextState})
            states[loop].out = emit(node.child, loop)
            nextState = loop
          else
            for _ = node.low + 1, node.high do
              nextState = state({kind = "split", out = emit(node.child, nextState), other = nextState})
            end
          end
          for _ = 1, node.low do nextState = emit(node.child, nextState) end
          return nextState
        elseif node.kind == "literal" then
          local letters = chars(node.value)
          for i = #letters, 1, -1 do
            nextState = state({kind = "consume", test = {kind = "literal", value = letters[i]}, out = nextState})
          end
          return nextState
        elseif node.kind == "start" or node.kind == "finish" or node.kind == "boundary" then
          return state({kind = node.kind, negate = node.negate, out = nextState})
        else return state({kind = "consume", test = node, out = nextState}) end
      end
      local start = emit(ast, state({kind = "accept"}))
      return function(text, budget)
        budget = budget or {remaining = 2000000}
        local letters, active, seen = chars(text), {}, {}
        local matched, exhausted = false, false
        local function spend()
          budget.remaining = budget.remaining - 1
          if budget.remaining < 0 then exhausted = true; return false end
          return true
        end
        local function add(id, pos, list, visited)
          local stack = {id}
          while #stack > 0 do
            local current = table.remove(stack)
            if not visited[current] then
              if not spend() then return end
              visited[current] = true
              local node = states[current]
              if node.kind == "accept" then matched = true; return
              elseif node.kind == "split" then stack[#stack + 1] = node.out; stack[#stack + 1] = node.other
              elseif node.kind == "consume" then list[#list + 1] = current
              elseif node.kind == "start" then
                if pos == 1 or letters[pos - 1] == "\n" then stack[#stack + 1] = node.out end
              elseif node.kind == "finish" then
                if pos > #letters or letters[pos] == "\n" then stack[#stack + 1] = node.out end
              elseif node.kind == "boundary" then
                local boundary = word(letters[pos - 1]) ~= word(letters[pos])
                if boundary ~= not not node.negate then stack[#stack + 1] = node.out end
              end
            end
          end
        end
        for pos = 1, #letters + 1 do
          local possible = not starts or starts[letters[pos]]
          if #active > 0 or possible then
            if possible then add(start, pos, active, seen) end
            if exhausted then return nil, "Regex is too complex; simplify the pattern." end
            if matched then return true end
            local following, visited = {}, {}
            for _, id in ipairs(active) do
              if not spend() then return nil, "Regex is too complex; simplify the pattern." end
              local node = states[id]
              if classMatch(node.test, letters[pos]) then add(node.out, pos + 1, following, visited) end
            end
            if exhausted then return nil, "Regex is too complex; simplify the pattern." end
            if matched then return true end
            active, seen = following, visited
          end
        end
        return false
      end
    end)
    if ok then return result end
    return nil, tostring(result)
  end
end
