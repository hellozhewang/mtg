-- Written guides are lazy/private, cache text, ignore pictures and never rebuild XML.
local checks = 0
local function check(v,m) checks=checks+1; assert(v,m) end
local attrs, requests, payloads = {}, {}, {}
UI={setAttribute=function(id,k,v) attrs[id]=attrs[id] or {};attrs[id][k]=v end,
 setCustomAssets=function() error("No guide picture loads") end,
 setXml=function() error("No guide XML rebuilds") end}
JSON={decode=function(v) return assert(payloads[v],"bad JSON") end}
WebRequest={get=function(url,cb) requests[#requests+1]={url=url,callback=cb} end}
CZ={base="https://example.test/",seats={"White","Red"},state={}}
Player={White={color="White",steam_id="white"},Red={color="Red",steam_id="red"}}
local white,red=Player.White,Player.Red
function czRender(c) local s=CZ.state[c];czgRender(c,s,s.selected) end
local function deck(id,guide) return {id=id,name=id,guide=guide,preview=id..".preview.json?v=1"} end
local function response(id)
 return {v=1,id=id,commanders={{faces={{FaceURL="never://download"}}}},guide={
  {title="Plan <unsafe>",rows={{name="A -> B",text=string.rep("Written strategy. ",250),
    cards={{faces={{FaceURL="never://download-card"}}}}}}}}}
end
dofile("tts/cactuar_guide.lua")
local s={open=true,player="white",selected=deck("a",true)};CZ.state.White=s
czRender("White")
check(#requests==0 and attrs.cz_guide_White.text=="Read guide","selection never fetches a guide or picture")
czGuide(red,nil,"cz_guide_White")
check(not s.guideOpen and #requests==0,"other seats cannot open a private guide")
czGuide(white,nil,"cz_guide_White")
check(s.guideOpen and #requests==1 and attrs.cz_guide_text_White.text=="Loading guide…","Read guide requests text lazily")
czRender("White");check(#requests==1,"pending guide redraws do not duplicate requests")
czGuideClose(white,nil,"cz_guide_back_White")
payloads.a=response("a");requests[1].callback({text="a"})
check(not s.guideOpen and attrs.cz_guide_view_White.active=="False","late guide content never reopens a closed view")
czGuide(white,nil,"cz_guide_White")
check(#requests==1 and attrs.cz_guide_text_White.text:find("Plan ‹unsafe›",1,true),"cached headings are safely escaped")
check(attrs.cz_guide_text_White.text:find("A → B",1,true),"combo names remain readable without images")
check(tonumber(attrs.cz_guide_text_White.height)>1000 and attrs.cz_guide_content_White.height==attrs.cz_guide_text_White.height,"long guides provide scrollable height")
check(CZ.guides[s.selected.preview].sections[1].rows[1].cards==nil,"guide picture metadata is discarded")
czGuideClose(red,nil,"cz_guide_back_White");check(s.guideOpen,"another seat cannot close a private guide")
CZ.state.Red={open=true,player="red",selected=s.selected};czRender("Red");czGuide(red,nil,"cz_guide_Red")
check(#requests==1 and CZ.state.Red.guideOpen,"seats share cached text but have separate views")
s.selected=deck("b",true);czRender("White")
check(not s.guideOpen and #requests==1,"changing decks closes the guide without requesting another")
czGuide(white,nil,"cz_guide_White");requests[2].callback({is_error=true})
check(attrs.cz_guide_text_White.text:find("Press Refresh",1,true),"failed guides explain retry")
czgRefresh();czRender("White");check(#requests==3,"Refresh retries a failed guide")
payloads.wrong=response("wrong");requests[3].callback({text="wrong"})
check(CZ.guides[s.selected.preview].status=="error","mismatched deck content is rejected")
s.selected=deck("none",false);czRender("White");czGuide(white)
check(not s.guideOpen and attrs.cz_guide_White.interactable=="False","decks without guides remain usable")
s.selected=deck("new",true);czRender("White");Player.White.steam_id="replacement"
czGuide(white,nil,"cz_guide_White")
check(not s.guideOpen and #requests==3,"old seat owners cannot open guides")
print(checks.." written guide checks, 0 failed")
