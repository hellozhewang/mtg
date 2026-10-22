-- Thumbnails are demand-loaded per chooser page, cacheable, and share UI safely.
local checks=0
local function check(v,m) checks=checks+1;assert(v,m) end
local attrs,assets,conditions,loads,redraws={},{{name="base",url="test://base"},{name="czsi_1",url="test://inspect"}},{},0,0
UI={loading=false,getCustomAssets=function()return assets end,
 setCustomAssets=function(value)assets=value;loads=loads+1;UI.loading=true end}
function czUI(id,k,v)attrs[id]=attrs[id] or {};attrs[id][k]=v end
Wait={condition=function(fn,condition)if condition()then fn()else conditions[#conditions+1]=fn end end}
local function finish()UI.loading=false;local pending=conditions;conditions={};for _,fn in ipairs(pending)do fn()end end
CZ={base="https://example.test/tts/",sleeveCells=8,seats={"White","Red"},index={sleeves={}},state={}}
for i=1,20 do CZ.index.sleeves[i]={id="s"..i,label="Sleeve "..i,thumb="sleeves/thumbs/"..i..".jpg"} end
Player={White={steam_id="white"},Red={steam_id="red"}}
CZ.state.White={open=true,player="white",query="current search",menuPage=1}
CZ.state.Red={open=false,player="red",query="private red",menuPage=1}
function czRender()redraws=redraws+1 end
function czRenderMenu()end
local inspectRedraws=0
function czsRedrawOpen()inspectRedraws=inspectRedraws+1 end
local picked
function czChoose(player,row)picked={player.color,row}end
dofile("tts/cactuar_sleeves.lua")
check(loads==0,"module load never downloads sleeves")
czslRender("White");check(loads==0,"rendering the browser without the chooser never loads thumbnails")
local s=CZ.state.White;s.menu="sleeve";czslRender("White")
check(loads==1 and #assets==10,"opening sleeves downloads only eight thumbnails plus existing shared assets")
check(attrs.cz_sl_1_White.interactable=="False","choices stay disabled while their thumbnails load")
czslRender("White");check(loads==1,"pending rendering never duplicates image requests")
finish()
check(attrs.cz_sl_img_1_White.image=="czsl_s1" and attrs.cz_sl_1_White.interactable=="True","loaded names and thumbnails bind before choosing")
check(attrs.cz_search_White.text=="current search" and redraws==1 and inspectRedraws==1,"shared asset completion restores current browser/search and Inspect sessions")
check(assets[1].name=="base" and assets[2].name=="czsi_1","base and Inspect assets survive registration")
czslRender("White");check(loads==1,"revisiting a cached sleeve page does not rebuild shared assets")
s.menuPage=2;czslRender("White");check(loads==2 and #assets==18,"next page loads only eight new thumbnails")
finish();s.menuPage=1;czslRender("White");check(loads==2,"returning to page one is cached")
s.menuPage=3;czslRender("White");check(loads==3 and #assets==22,"last page registers only remaining thumbnails")
s.open=false;s.menu=nil
finish()
check(attrs.cz_panel_White.active=="False","late sleeve completion cannot reopen a closed browser")
s.open=true;s.menu="sleeve";s.menuPage=1;czslRender("White")
check(loads==3,"reopening the chooser uses cached thumbnails")
CZ.index.sleeves[1].thumb="sleeves/thumbs/new-1.jpg";czslRender("White")
check(loads==4,"changed artwork updates when its page is explicitly opened")
finish()
local red=CZ.state.Red;red.open=true;red.menu="sleeve";red.menuPage=3
CZ.index.sleeves[20].thumb="sleeves/thumbs/new-20.jpg";czslRender("Red");finish()
check(attrs.cz_sl_img_1_Red.image=="czsl_s17" and attrs.cz_sl_img_1_White.image=="czsl_s1","simultaneous chooser pages keep each seat's pictures")
check(attrs.cz_search_Red.text=="private red","another seat's search survives shared picture loading")
CZ.index.sleeves[2].thumb=nil;czslRender("White")
check(attrs.cz_sl_img_2_White.image=="" and attrs.cz_sl_name_2_White.text=="Sleeve 2","a sleeve without a thumbnail retains its name without loading full-size art")
czSleevePick({color="White"},"2")
check(picked[1]=="White" and picked[2]=="2","thumbnail selection uses the existing private sleeve handler")
print(checks.." lazy sleeve checks, 0 failed")
