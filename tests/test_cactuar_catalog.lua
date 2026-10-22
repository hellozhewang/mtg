-- Catalog decoding yields between small records and commits only a complete index.
local checks=0
local function check(v,m)checks=checks+1;assert(v,m)end
local jobs,decoded={},{}
Wait={frames=function(fn)jobs[#jobs+1]=fn end}
local function frame()
 local current=jobs;jobs={}
 for _,fn in ipairs(current)do fn()end
end
local function drain()for _=1,100 do if #jobs==0 then return end;frame()end;error("parser did not settle")end
JSON={decode=function(raw)
 decoded[#decoded+1]=raw
 if raw=="header" then return {v=1,count=5,tiers={},themes={},sleeves={},tournament={}}end
 if raw=="empty" then return {v=1,count=0,tiers={},themes={}}end
 if raw=="bad-header" then return {v=1,count=-1,tiers={},themes={}}end
 if raw:match("^deck%d$")then
  return {id=raw,name=raw.." \"quoted\" — 中文",commander="A & B",owner="owner",cap=nil}
 end
 error("invalid JSON")
end}
dofile("tts/cactuar_catalog.lua")
local feed="header\ndeck1\ndeck2\ndeck3\ndeck4\ndeck5\n"
local result,err,completed,progress=nil,nil,0,{}
czDecodeCatalog(feed,function(v,e)result,err,completed=v,e,completed+1 end,function(n,total)progress[#progress+1]={n,total}end)
check(#decoded==0 and not result,"clicking/fetching does not synchronously decode the full catalog")
frame();check(#decoded==2 and completed==0,"the first frame decodes at most two small records")
frame();check(#decoded==4 and completed==0,"later frames remain bounded and partial catalogs stay private")
drain()
check(completed==1 and result and not err and #result.decks==5,"the full index commits exactly once after all records validate")
check(result.decks[1].name=='deck1 "quoted" — 中文' and result.decks[1].commander=="A & B","native JSON values survive unchanged")
check(progress[#progress][1]==5 and progress[#progress][2]==5,"progress includes the declared full catalog count")
local function fails(text,pattern)
 result,err,completed=nil,nil,0
 czDecodeCatalog(text,function(v,e)result,err,completed=v,e,completed+1 end)
 drain()
 check(not result and completed==1 and err:find(pattern,1,true),"reject invalid feed: "..pattern)
end
fails("header\ndeck1\n","incomplete")
fails("header\ndeck1\ndeck1\n","invalid deck")
fails("empty\ndeck1\n","invalid deck")
fails("bad-header\n","header")
fails("header\nbroken\n","JSON records")
fails(string.rep("x",32769).."\n","too large")
result=nil
czDecodeCatalog("empty\n\n",function(v)result=v end);drain()
check(result and #result.decks==0,"empty catalogs and trailing blank lines are valid")
local alive=true;completed=0
czDecodeCatalog(feed,function()completed=completed+1 end,nil,function()return alive end)
frame();local before=#decoded;alive=false;drain()
check(completed==0 and #decoded==before,"superseded browser instances stop decoding and cannot commit old results")
-- A slow native record exhausts the time budget even before the count limit.
local clock=os.clock;local now=0
os.clock=function()return now end
local decode=JSON.decode
JSON.decode=function(raw)local value=decode(raw);now=now+0.02;return value end
decoded={};result=nil
czDecodeCatalog(feed,function(v)result=v end)
frame();check(#decoded==1,"a slow header yields before decoding any deck in the same frame")
frame();check(#decoded==2,"a slow record yields before reaching the two-record limit")
drain();check(result and #result.decks==5,"time-budget yields still complete the full catalog")
os.clock=clock;JSON.decode=decode
print(checks.." incremental catalog checks, 0 failed")
