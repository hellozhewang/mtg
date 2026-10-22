local checks=0
local function check(v,m)checks=checks+1;assert(v,m)end
local attrs,requests,jobs,callbacks={},{},{},{}
UI={setCustomAssets=function()error("commander text must not load images")end,setXml=function()error("no shared XML rebuild")end}
CZ={base="test://",state={},commanderTexts={}}
Player={White={steam_id="white"},Red={steam_id="red"}}
function czUI(id,k,v)attrs[id]=attrs[id]or{};attrs[id][k]=v end
Wait={frames=function(fn)jobs[#jobs+1]=fn end}
WebRequest={get=function(url,cb)requests[#requests+1]=url;callbacks[url]=cb end}
local face={name="First",mana_cost="{2}{U}",type_line="Legendary Creature — Wizard",oracle_text="Draw a card.\n<Read> & learn.",power="2",toughness="3",loyalty="",defense=""}
local function card(name,loyalty)
 local f={};for k,v in pairs(face)do f[k]=v end
 f.name=name
 if loyalty then f.power,f.toughness,f.loyalty="","",loyalty end
 return {name=name,mv=3,faces={f}}
end
JSON={decode=function(raw)
 if raw=="head"then return {v=1,id="pair",count=2}end
 if raw=="dualhead"then return {v=1,id="dual",count=1}end
 if raw=="dualcard"then
  local c=card("Front");local back={};for k,v in pairs(c.faces[1])do back[k]=v end
  back.name="Back";back.mana_cost="{3}{B}";c.faces[2]=back;return c
 end
 if raw=="one"then return card("First")end
 if raw=="two"then return card("Second","4")end
 error("bad JSON")
end}
local deck={id="pair",commander_text="pair.commander.jsonl?v=123"}
local s={open=true,player="white",selected=deck};CZ.state.White=s
function czRender(c)local state=CZ.state[c];czcRender(c,state,state.selected)end
local function drain()
 for _=1,20 do if #jobs==0 then return end;local pending=jobs;jobs={};for _,fn in ipairs(pending)do fn()end end
 error("pending commander decode")
end
dofile("tts/cactuar_commander.lua")
check(#requests==0,"module load does not fetch commander data")
czcRender("White",s,nil);check(#requests==0 and attrs.cz_commander_White.active=="False","no selection hides the area without fetching")
czcRender("White",s,deck)
check(#requests==1 and attrs.cz_commander_text_White.text:find("Loading",1,true),"selection fetches only its small text file")
czcRender("White",s,deck);check(#requests==1,"pending redraw deduplicates commander requests")
callbacks[requests[1]]({text="head\none\ntwo\n"})
check(#jobs==1 and attrs.cz_commander_text_White.text:find("Loading",1,true),"HTTP completion defers record decoding to native frames")
drain()
local text=attrs.cz_commander_text_White.text
check(text:find("{2}{U}",1,true) and text:find("Mana value (CMC): 3",1,true),"mana cost and value are readable")
check(text:find("Legendary Creature",1,true) and text:find("Draw a card.",1,true),"type and full rules are shown")
check(text:find("P/T: 2/3",1,true) and text:find("Loyalty: 4",1,true),"creature and planeswalker stats are shown")
check(text:find("First",1,true)<text:find("Second",1,true),"partners keep commander order")
check(text:find("‹Read› & learn.",1,true) and not text:find("<Read>",1,true),"card text cannot inject rich-text tags")
check(tonumber(attrs.cz_commander_content_White.height)>150,"scroll content has room for all rules")
czcRender("White",s,deck);check(#requests==1,"cached selection does not download again")
local other={id="other",commander_text="other.commander.jsonl"}
s.selected=other;czcRender("White",s,other)
s.selected=deck;czcRender("White",s,deck)
callbacks[requests[2]]({is_error=true})
check(attrs.cz_commander_text_White.text==text,"a late error for an old selection cannot replace current text")
czcRefresh();s.selected=other;czcRender("White",s,other)
check(#requests==3,"Refresh allows a failed commander request to retry")
s.open=false
callbacks[requests[3]]({text="bad"});drain()
check(not s.open,"late completion cannot reopen a closed panel")
local before=#requests;czcRender("White",s,deck)
check(#requests==before,"closed panels never initiate text downloads")
s.open=true;s.selected={id="legacy"};czcRender("White",s,s.selected)
check(attrs.cz_commander_text_White.text:find("unavailable",1,true),"older catalogs remain usable without commander data")
s.selected={id="dual",commander_text="dual.commander.jsonl"};czcRender("White",s,s.selected)
callbacks[requests[#requests]]({text="dualhead\ndualcard\n"});drain()
local dual=attrs.cz_commander_text_White.text
check(dual:find("Front mana value (CMC): 3",1,true) and dual:find("Mana cost: {3}{B}",1,true),"double-faced cards label the front's stored value and show each face's own cost")
check(dual:find("Front",1,true)<dual:find("Back",1,true),"multiple faces retain their order")
print(checks.." commander text checks, 0 failed")
