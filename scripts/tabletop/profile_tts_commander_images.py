#!/usr/bin/env python3
"""Measure temporary commander images on the running TTS host; never build/upload.

    python3 scripts/tabletop/profile_tts_commander_images.py --hold
    python3 scripts/tabletop/profile_tts_commander_images.py --cleanup

Requires tts/deploy.local.json, a loaded Cactuar browser and its scripting server.
The --hold option keeps the last picture visible for a screenshot until --cleanup.
Artifacts contain the original UI/assets and a timing report under .cache/.
"""
from __future__ import annotations
import argparse
import base64
import json
from pathlib import Path
import shlex
import time
import uuid
import xml.etree.ElementTree as ET
from release_tts import PC, CONFIG, REPO, windows_path


class Editor:
    def __init__(self, pc: PC):
        self.pc = pc
        self.folder = pc.workshop_dir + '/commander-profile-' + uuid.uuid4().hex
        pc.shell('mkdir -p ' + shlex.quote(self.folder))

    def execute(self, script: str):
        path = self.folder + '/' + uuid.uuid4().hex + '.json'
        win = windows_path(path)
        payload = json.dumps({'messageID': 3, 'guid': '-1', 'script': script, 'returnID': 101}).encode()
        self.pc.shell('cat > ' + shlex.quote(path), payload)
        ps = r'''
$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue'
[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false)
$l=[System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::IPv6Any,39998)
$l.Server.DualMode=$true
try {
 $l.Start();$c=[System.Net.Sockets.TcpClient]::new('localhost',39999)
 $b=[System.IO.File]::ReadAllBytes('__FILE__');$c.GetStream().Write($b,0,$b.Length)
 $deadline=[DateTime]::UtcNow.AddSeconds(12);$found=$null
 while ([DateTime]::UtcNow -lt $deadline) {
  while (-not $l.Pending() -and [DateTime]::UtcNow -lt $deadline) {Start-Sleep -Milliseconds 50}
  if (-not $l.Pending()) {break}
  $r=$l.AcceptTcpClient();$s=$r.GetStream();$s.ReadTimeout=5000
  $buffer=[byte[]]::new(65536);$all=[System.IO.MemoryStream]::new();$parsed=$null
  while ($true) {
   $n=$s.Read($buffer,0,$buffer.Length);if ($n -eq 0) {break}
   $all.Write($buffer,0,$n);$j=[System.Text.Encoding]::UTF8.GetString($all.ToArray())
   try {$parsed=ConvertFrom-Json -InputObject $j;break} catch {}
  }
  $r.Close()
  if ($parsed -and $parsed.messageID -eq 5 -and $parsed.returnID -eq 101) {$found=$j;break}
 }
 if (-not $found) {throw 'No matching TTS editor reply'}
 [Console]::Write($found)
} finally {if ($c) {$c.Close()};$l.Stop();Remove-Item -LiteralPath '__FILE__' -ErrorAction SilentlyContinue}
'''.replace('__FILE__', win.replace("'", "''"))
        encoded = base64.b64encode(ps.encode('utf-16le')).decode()
        response = self.pc.shell('powershell.exe -NoProfile -NonInteractive -EncodedCommand ' + encoded, timeout=25)
        reply = json.loads(response.lstrip('\ufeff'))
        value = reply.get('returnValue')
        result = json.loads(value) if isinstance(value, str) else value
        if isinstance(result, dict) and result.get('ok') is False:
            raise RuntimeError(result.get('error', result))
        return result

    def close(self):
        self.pc.shell('rmdir ' + shlex.quote(self.folder))


def lua_string(text):
    assert ']====]' not in text
    return '[====[' + text + ']====]'


def cleanup(editor, output):
    print(editor.execute('CZPB.cleanup();return JSON.encode({phase=CZPB.phase})'), flush=True)
    for _ in range(10):
        status = editor.execute('return JSON.encode({phase=CZPB.phase,restored=CZPB.restored or false,assets=#UI.getCustomAssets(),loading=UI.loading})')
        if status.get('restored'):
            (output / 'restored.json').write_text(json.dumps(status, indent=2)+'\n')
            print(status, flush=True)
            editor.execute('CZPB=nil;return JSON.encode({benchmarkReleased=true})')
            return
        time.sleep(1)
    raise RuntimeError('Cleanup did not finish; original UI is saved in before-ui.json')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--hold', action='store_true')
    ap.add_argument('--cleanup', action='store_true')
    ap.add_argument('--output', type=Path, default=REPO / '.cache/commander-image-profile')
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    editor = Editor(PC(json.loads(CONFIG.read_text())))
    started = success = False
    try:
        if args.cleanup:
            cleanup(editor, args.output)
            return
        snapshot = editor.execute('''local ok,r=pcall(function()
 assert(CZ and CZ.index and CZ.state.White and CZ.state.White.open,"Open White's Cactuar browser first")
 assert(not UI.loading and not CZ.fetching and not CZ.sleeveLoading,"UI/catalog busy")
 assert(not CZPB or CZPB.restored,"Previous profile still needs cleanup")
 assert(not next(CZS.state),"Close Inspect before measuring")
 return {xml=UI.getXml(),assets=UI.getCustomAssets(),selected=CZ.state.White.selected and CZ.state.White.selected.id,
  time=Time.time,frame_count=Time.frame_count,delta_time=Time.delta_time}
 end) return JSON.encode({ok=ok,result=r,error=not ok and tostring(r) or nil})''')['result']
        (args.output / 'before-ui.json').write_text(json.dumps(snapshot, indent=2)+'\n')
        index = json.loads((REPO / 'docs/tts/decks.json').read_text())
        ids = ['digitalstealth/Belakor-Demons', 'kupo7/Yuna-Counters', 'zzwang/Giada-Angels']
        urls = [next(d for d in index['decks'] if d['id']==ident)['commanders'][0]['faces'][0]['FaceURL'] for ident in ids]
        nonce = uuid.uuid4().hex
        fresh = [u + ('&' if '?' in u else '?') + 'cz_profile=' + nonce for u in urls]
        panel = '<Panel id="czpbench_root" raycastTarget="false">'
        for color in ['White','Red','Yellow','Green','Blue','Purple']:
            panel += f'''<Panel id="czpbench_panel_{color}" visibility="{color}" active="False" width="234" height="348"
 rectAlignment="MiddleRight" offsetXY="-18 0" color="#1A2635" raycastTarget="false">
 <Text width="220" height="20" rectAlignment="UpperCenter" text="Temporary image benchmark" fontSize="11" color="#C0C8D2" raycastTarget="false"/>
 <Image id="czpbench_image_{color}" width="220" height="308" rectAlignment="LowerCenter" preserveAspect="true" color="#FFFFFF00" raycastTarget="false"/>
 </Panel>'''
        panel += '</Panel>'
        test_xml = snapshot['xml'] + panel
        ET.fromstring('<root>' + test_xml + '</root>')
        cfg = {'ids':ids,'urls':urls,'freshUrls':fresh}
        start = '''local ok,r=pcall(function()
 local cfg=JSON.decode('''+lua_string(json.dumps(cfg))+''')
 CZPB={originalXml=UI.getXml(),testXml='''+lua_string(test_xml)+''',wasOpen=CZ.state.White.open,decks={},urls=cfg.urls,freshUrls=cfg.freshUrls}
 for _,id in ipairs(cfg.ids) do
  for _,d in ipairs(CZ.index.decks) do if d.id==id then CZPB.decks[#CZPB.decks+1]=d;break end end
 end
 assert(#CZPB.decks==#cfg.ids,"Sample deck missing from live catalog")
 '''+(REPO/'scripts/tabletop/profile_tts_commander_images.lua').read_text()+'''
 return {phase=CZPB.phase}
 end) return JSON.encode({ok=ok,result=r,error=not ok and tostring(r) or nil})'''
        print(editor.execute(start), flush=True);started=True
        deadline = time.monotonic()+180
        while time.monotonic()<deadline:
            time.sleep(3)
            status = editor.execute('return JSON.encode({phase=CZPB.phase,running=CZPB.running,completed=#CZPB.results,error=CZPB.error})')
            print(status, flush=True)
            if status.get('error'):raise RuntimeError(status['error'])
            if not status.get('running'):break
        else:raise RuntimeError('Benchmark timed out')
        report = editor.execute('return JSON.encode({phase=CZPB.phase,results=CZPB.results,assets=#UI.getCustomAssets(),loading=UI.loading})')
        report['images'] = cfg
        report['limitations'] = ['Host-only frame timings; not remote clients.',
            'First registration may use disk cache; fresh query URLs exercise a new URL without clearing user caches.',
            'UI.loading=false is readiness, not visual proof; capture the held picture.',
            'Image widgets use a temporary overlay; full browser layout changes and new-game startup are not measured.',
            'Lua sampling and editor polling contribute small overhead; compare repeated controls.']
        (args.output / 'results.json').write_text(json.dumps(report,indent=2)+'\n')
        print('Saved',args.output/'results.json',flush=True)
        success = True
    finally:
        if started and (not args.hold or not success):
            cleanup(editor, args.output)
        editor.close()


if __name__ == '__main__':
    main()
