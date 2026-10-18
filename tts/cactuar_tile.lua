--[[ Cactuar tile: the script on each Cactuar tile scripts/build_tts_table.py
  puts on the table (source: github.com/hellozhewang/mtg, tts/). Clicking the
  tile opens the clicker's own deck browser, which lives in the Global script
  (tts/cactuar.lua). ]]

function onLoad()
  self.createButton({
    click_function = "czTileClick",
    function_owner = self,
    tooltip = "Browse the Cactuar decks",
    position = {0, 0.1, 0},
    width = 1000,                     -- the whole tile
    height = 1000,
    color = {1, 1, 1, 0},
    hover_color = {1, 1, 1, 0.12},
    press_color = {1, 1, 1, 0.25},
    label = "",
  })
end

function czTileClick(_, color)
  Global.call("czOpenFor", {color = color})
end
