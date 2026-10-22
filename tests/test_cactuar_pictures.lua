-- Commander picture demand, native asset coordination and privacy regression checks.
local checks=0
local function check(v,m) checks=checks+1;assert(v,m) end
local attrs,assets,loads,conditions,frames={},{
 {name="base",url="test://base",type=1},
 {name="czsi_1",url="https://example.test/inspect.webp"},
 {name="czsl_one",url="https://example.test/sleeve.jpg"}},0,{},{}
UI={loading=false,getCustomAssets=function()return assets end,
 setXml=function()error("picture loading must not replace XML")end,
 setCustomAssets=function(a)assets=a;loads=loads+1;UI.loading=true end}
function czUI(id,k,v)attrs[id]=attrs[id]or{};attrs[id][k]=v end
local frameNumber=0
Wait={frames=function(fn,delay)frames[#frames+1]={fn=fn,at=frameNumber+(delay or 1)} end,
 condition=function(fn,condition,timeout,onTimeout)
  conditions[#conditions+1]={fn=fn,test=condition,timeout=onTimeout}
 end}
local function frame()
 frameNumber=frameNumber+1
 local queued=frames;frames={};for _,job in ipairs(queued)do if job.at<=frameNumber then job.fn()else frames[#frames+1]=job end end
 local pending=conditions;conditions={}
 for _,c in ipairs(pending)do if c.test()then c.fn()else conditions[#conditions+1]=c end end
end
local function drain(n)for _=1,n or 12 do frame()end end
local function finish()UI.loading=false;drain()end
local function deck(id,urls)
 local faces={}
 for i,url in ipairs(urls or {})do faces[i]={name=id.." face "..i,FaceURL=url}end
 return {id=id,commanders={{name=id,faces=faces}}}
end
local a=deck("A",{"https://example.test/a.webp","https://example.test/a-back.webp"})
a.commanders[2]={name="Partner",faces={{name="Partner",FaceURL="https://example.test/partner.webp"}}}
local b=deck("B",{"https://example.test/b.webp"})
local shared=deck("Shared",{"https://example.test/a.webp"})
CZ={state={},seats={"White","Red"},base="https://example.test/tts/",index={sleeves={}},sleeveCells=8}
Player={White={steam_id="white"},Red={steam_id="red"}}
local s={open=true,player="white",selected=a,query="keep my search"}
local red={open=true,player="red",selected=b,query="private red"}
CZ.state.White,CZ.state.Red=s,red
local inspectRedraws=0
function czsRedrawOpen()inspectRedraws=inspectRedraws+1 end
function czRender(c)local state=CZ.state[c];czcpRender(c,state,state.selected)end
function czRenderMenu()end
local white,other= {color="White"},{color="Red"}
local function has(url)for _,v in ipairs(assets)do if v.url==url then return true end end end
local function faceURL(id)
 for _,a in ipairs(assets)do if a.name==(attrs[id]or{}).image then return a.url end end
end
dofile("tts/cactuar_pictures.lua")
czRender("White");czRender("Red")
check(loads==0,"initial browser render never requests pictures")
s.selected=b;czRender("White");s.selected=a;czRender("White")
check(loads==0 and not s.pictureOpen,"changing decks remains text-only even with image metadata")
czPictureShow(other,nil,"cz_commander_show_White")
check(loads==0,"another seat cannot request a private picture")
czPictureShow(white,nil,"cz_commander_show_White")
check(loads==1 and CZ.pictureLoading and #assets==4,"Show picture registers only the selected first face")
check(not has("https://example.test/a-back.webp")and not has("https://example.test/partner.webp"),"alternate faces and partners are not prefetched")
check(assets[1].name=="base"and assets[1].type==1 and assets[2].name=="czsi_1"and assets[3].name=="czsl_one","fonts, Inspect and sleeve assets survive")
check(attrs.cz_picture_image_White.image==""and attrs.cz_picture_White.active=="True","opening clears stale art and shows loading without a white placeholder")
czRender("White");check(loads==1,"redraw during loading does not repeat asset registration")
finish()
check(not CZ.pictureLoading and faceURL("cz_picture_image_White")=="https://example.test/a.webp","settled native loading binds the current face")
czPictureClose(white);czPictureShow(white)
check(attrs.cz_picture_image_White.image==""and attrs.cz_picture_image_White.color=="#FFFFFF00","cached binding forces a blank transparent image before its delayed sprite")
frame();check(attrs.cz_picture_image_White.image=="","sprite is not assigned in the same frame as the blank transition")
frame();check(faceURL("cz_picture_image_White")=="https://example.test/a.webp","post-ready blank-to-sprite transition binds on a later native frame")
check(attrs.cz_picture_page_White.text=="1 / 3"and attrs.cz_picture_prev_White.interactable=="False","ordered partners/faces share a bounded preview pager")
check(attrs.cz_search_White.text=="keep my search"and attrs.cz_search_Red.text=="private red"and inspectRedraws==1,"shared completion restores current searches and Inspect")
local n=loads
czPictureClose(white);czPictureShow(white);drain()
check(loads==n and faceURL("cz_picture_image_White")=="https://example.test/a.webp","cached reopen binds without a native asset rebuild")
czPictureStep(white,"next","cz_picture_next_White");check(loads==n+1,"explicit next loads only the next face")
finish();check(faceURL("cz_picture_image_White")=="https://example.test/a-back.webp","double-faced back keeps its actual pinned URL")
czPictureStep(white,"next");finish()
check(attrs.cz_picture_name_White.text=="Partner"and attrs.cz_picture_page_White.text=="3 / 3","second commander follows the first commander's faces")
n=loads;czPictureStep(white,"next");czPictureStep(white,"invalid")
check(loads==n,"pager bounds/forged directions do not fetch")
czPictureStep(white,"prev");czPictureStep(white,"prev");drain()
check(loads==n and faceURL("cz_picture_image_White")=="https://example.test/a.webp","previous faces use retained assets")
s.selected=b;czRender("White")
check(not s.pictureOpen and attrs.cz_picture_image_White.image==""and loads==n,"selecting a new deck closes the picture without fetching it")
czPictureShow(white);check(loads==n+1,"new commander registers only on explicit request")
s.open=false;s.pictureOpen=false;finish()
check(not s.open and attrs.cz_panel_White.active=="False","completion cannot reopen a closed browser")
s.open=true;s.selected=shared;czRender("White");czPictureShow(white);drain()
check(loads==n+1 and faceURL("cz_picture_image_White")=="https://example.test/a.webp","different decks sharing a pinned URL reuse one asset")
-- While another UI operation is busy, demand coalesces to the newest valid face.
czPictureClose(white);UI.loading=true;s.selected=a;czRender("White");czPictureShow(white);czPictureStep(white,"next")
n=loads;s.selected=b;czRender("White");finish()
check(loads==n and not s.pictureOpen,"changing deck cancels queued demands before any native load")
local fresh=deck("Fresh",{"https://example.test/fresh.webp","https://example.test/fresh-back.webp"})
s.selected=fresh;czRender("White");UI.loading=true;czPictureShow(white);czPictureStep(white,"next")
finish()
check(loads==n+1 and not has("https://example.test/fresh.webp")and has("https://example.test/fresh-back.webp"),"pending pagination loads only the last explicitly requested face")
finish();check(faceURL("cz_picture_image_White")=="https://example.test/fresh-back.webp","coalesced face is the one painted after completion")
czPictureClose(white);s.selected=deck("Closed",{"https://example.test/closed.webp"});czRender("White")
UI.loading=true;czPictureShow(white);czPictureClose(white);n=loads;finish()
check(loads==n and attrs.cz_picture_White.active=="False","closing the picture cancels a queued load")
s.selected=deck("Owner",{"https://example.test/owner.webp"});czRender("White")
UI.loading=true;czPictureShow(white);Player.White.steam_id="replacement";n=loads;finish()
check(loads==n and attrs.cz_panel_White.active=="False","a changed seat owner cannot inherit a queued request/window")
Player.White.steam_id="white";s.pictureOpen=false
s.selected={id="legacy"};czRender("White");czPictureShow(white)
check(loads==n and attrs.cz_commander_show_White.interactable=="False","legacy catalogs without images remain usable")
-- A shared rebuild invalidates stale binding writes; render never queues demand.
s.selected=a;czRender("White");czPictureShow(white)
attrs.cz_picture_image_White.image=""
CZ.imageGeneration=(CZ.imageGeneration or 0)+1;czRender("White");drain()
check(faceURL("cz_picture_image_White")=="https://example.test/a.webp"and loads==n,"native redraw can rebind cached art without loading new URLs")
-- Integrate the real sleeve queue: waiting for pictures must not deadlock either.
CZ.index.sleeves={{id="new",label="New",thumb="sleeves/new.jpg"}}
dofile("tts/cactuar_sleeves.lua")
s.selected=deck("Overlap",{"https://example.test/overlap.webp"});czRender("White");czPictureShow(white)
s.menu,s.menuPage="sleeve",1;czslRequest("White")
check(CZ.pictureLoading and CZ.sleeveLoading,"sleeves can queue while the requested commander is loading")
finish();finish()
check(not CZ.pictureLoading and not CZ.sleeveLoading and has(CZ.base.."sleeves/new.jpg"),"picture and sleeve queues settle without a mutual wait")
check(has("https://example.test/overlap.webp")and has("https://example.test/a.webp"),"loading a sleeve page retains previously requested commander faces")
s.menu=nil
-- Exact changed URL is a new asset; unchanged URL does not rebuild.
n=loads;czPictureClose(white);s.selected=deck("Pinned",{"https://example.test/a.webp?v=2"});czRender("White");czPictureShow(white);finish()
check(loads==n+1 and faceURL("cz_picture_image_White")=="https://example.test/a.webp?v=2","changed/versioned picture URLs are not confused with old pinned art")
-- Expanding Inspect defers explicit requests and keeps their demands cancellable.
s.selected=deck("InspectWait",{"https://example.test/inspect-wait.webp"});czRender("White")
CZS={rebuilding=true};n=loads;czPictureShow(white);drain()
check(loads==n,"picture registration waits for Inspect's native rebuild")
CZS.rebuilding=false;drain();finish()
check(loads==n+1 and faceURL("cz_picture_image_White")=="https://example.test/inspect-wait.webp","an explicit request resumes after Inspect settles")
CZS=nil
-- A catalog replacement of the same ID must not inherit the old face demand.
czPictureClose(white);s.selected=deck("Replace",{"https://example.test/old-replace.webp"});czRender("White")
UI.loading=true;czPictureShow(white)
s.selected=deck("Replace",{"https://example.test/new-replace.webp"});czRender("White");n=loads;finish()
check(loads==n and not s.pictureOpen and not has("https://example.test/old-replace.webp"),"replaced metadata cancels stale URLs without fetching the replacement automatically")
-- Two players explicitly requesting different pictures share one pending update.
s.selected=deck("WhiteLater",{"https://example.test/white-later.webp"});red.selected=deck("RedLater",{"https://example.test/red-later.webp"})
czRender("White");czRender("Red");UI.loading=true
czPictureShow(white);czPictureShow(other);n=loads;finish()
check(loads==n+1 and has("https://example.test/white-later.webp")and has("https://example.test/red-later.webp"),"two current explicit demands batch into one native asset registration")
finish()
check(faceURL("cz_picture_image_White")=="https://example.test/white-later.webp"and faceURL("cz_picture_image_Red")=="https://example.test/red-later.webp","simultaneous previews keep their own requested faces")
-- Bounded failure: a stalled shared loader reports an error instead of retrying.
czPictureClose(white);s.selected=deck("Timeout",{"https://example.test/timeout.webp"});czRender("White")
UI.loading=true;czPictureShow(white);drain(1)
local timeout=conditions[#conditions].timeout;conditions={};timeout()
check(not CZ.pictureLoading and attrs.cz_picture_status_White.text:find("timed out",1,true),"loading timeout leaves an actionable error and releases the picture queue")
n=loads;drain()
check(loads==n,"a loading error does not automatically retry or register images")
UI.loading=false;czPictureClose(white);czPictureShow(white);finish()
check(loads==n+1 and faceURL("cz_picture_image_White")=="https://example.test/timeout.webp","explicit close/reopen retries a failed pending request")
print(checks.." commander picture checks, 0 failed")
