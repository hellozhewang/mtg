# Update a Tabletop Simulator Steam Workshop item, the way TTS's own uploader does.
#
# TTS uses Steam's legacy Workshop (ISteamRemoteStorage): an item is one file in the
# player's TTS Steam Cloud, published. SteamCMD can't update those ("no workshop depot
# found"), so this calls the same API through the steam_api64.dll that ships with TTS:
#   write the file and the preview to TTS's Steam Cloud, then update the item's file,
#   preview and change note, and wait for Steam's verdict.
#
# Runs on the owner's PC inside their logged-in Windows session (scripts/release_tts.py
# starts it as a one-off scheduled task), because the Steam API talks to the running
# Steam client. It uses whatever account that client is logged in as; it never sees a
# password. It keeps the existing PowerShell policy. The result is written as JSON.
#
# Its one argument is a JSON file (a scheduled task's command line is short, and change
# notes have quotes): {"dll": TTS's Plugins\x86_64\steam_api64.dll, "item": the Workshop
# item id, "file": the save as BSON, "preview": the preview picture, "note": the change
# note, "result": where to write the result}.
param([Parameter(Mandatory)] [string] $Config)
$ErrorActionPreference = "Stop"
$cfg = Get-Content -Raw -Encoding UTF8 $Config | ConvertFrom-Json
$Dll, $Item, $File, $Preview, $Note, $Result = $cfg.dll, [UInt64]$cfg.item, $cfg.file, $cfg.preview, "$($cfg.note)", $cfg.result
$TtsApp = 286160
$CloudFile = "WorkshopUpload"                  # TTS's own name for an item's file
$CloudPreview = "WorkshopUploadPreview.png"

function Finish($ok, $message, $extra = @{}) {
  $out = @{ ok = $ok; message = $message; time = (Get-Date).ToString("o") } + $extra
  $out | ConvertTo-Json -Compress | Set-Content -Path "$Result.tmp" -Encoding UTF8
  Move-Item -LiteralPath "$Result.tmp" -Destination $Result -Force
  exit ([int](-not $ok))
}

$initialized = $false
try {
  $env:SteamAppId = "$TtsApp"
  $env:SteamGameId = "$TtsApp"
  Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class CzSteam {
  const string D = @"$Dll";
  [DllImport(D, CallingConvention = CallingConvention.Cdecl)] public static extern int SteamAPI_InitFlat([Out] byte[] err);
  [DllImport(D, CallingConvention = CallingConvention.Cdecl)] public static extern void SteamAPI_RunCallbacks();
  [DllImport(D, CallingConvention = CallingConvention.Cdecl)] public static extern void SteamAPI_Shutdown();
  [DllImport(D, CallingConvention = CallingConvention.Cdecl)] public static extern IntPtr SteamAPI_SteamRemoteStorage_v016();
  [DllImport(D, CallingConvention = CallingConvention.Cdecl)] public static extern IntPtr SteamAPI_SteamUtils_v010();
  [DllImport(D, CallingConvention = CallingConvention.Cdecl)] public static extern IntPtr SteamAPI_SteamUser_v023();
  [DllImport(D, CallingConvention = CallingConvention.Cdecl)] public static extern ulong SteamAPI_ISteamUser_GetSteamID(IntPtr self);
  [DllImport(D, CallingConvention = CallingConvention.Cdecl)] [return: MarshalAs(UnmanagedType.I1)]
  public static extern bool SteamAPI_ISteamUser_BLoggedOn(IntPtr self);
  [DllImport(D, CallingConvention = CallingConvention.Cdecl)] public static extern uint SteamAPI_ISteamUtils_GetAppID(IntPtr self);
  [DllImport(D, CallingConvention = CallingConvention.Cdecl)] [return: MarshalAs(UnmanagedType.I1)]
  public static extern bool SteamAPI_ISteamRemoteStorage_FileWrite(IntPtr self, [MarshalAs(UnmanagedType.LPStr)] string file, byte[] data, int cub);
  [DllImport(D, CallingConvention = CallingConvention.Cdecl)]
  public static extern ulong SteamAPI_ISteamRemoteStorage_CreatePublishedFileUpdateRequest(IntPtr self, ulong item);
  [DllImport(D, CallingConvention = CallingConvention.Cdecl)] [return: MarshalAs(UnmanagedType.I1)]
  public static extern bool SteamAPI_ISteamRemoteStorage_UpdatePublishedFileFile(IntPtr self, ulong handle, [MarshalAs(UnmanagedType.LPStr)] string file);
  [DllImport(D, CallingConvention = CallingConvention.Cdecl)] [return: MarshalAs(UnmanagedType.I1)]
  public static extern bool SteamAPI_ISteamRemoteStorage_UpdatePublishedFilePreviewFile(IntPtr self, ulong handle, [MarshalAs(UnmanagedType.LPStr)] string file);
  [DllImport(D, CallingConvention = CallingConvention.Cdecl)] [return: MarshalAs(UnmanagedType.I1)]
  public static extern bool SteamAPI_ISteamRemoteStorage_UpdatePublishedFileSetChangeDescription(IntPtr self, ulong handle, [MarshalAs(UnmanagedType.LPUTF8Str)] string note);
  [DllImport(D, CallingConvention = CallingConvention.Cdecl)]
  public static extern ulong SteamAPI_ISteamRemoteStorage_CommitPublishedFileUpdate(IntPtr self, ulong handle);
  [DllImport(D, CallingConvention = CallingConvention.Cdecl)] [return: MarshalAs(UnmanagedType.I1)]
  public static extern bool SteamAPI_ISteamUtils_IsAPICallCompleted(IntPtr self, ulong call, [MarshalAs(UnmanagedType.I1)] out bool failed);
  [DllImport(D, CallingConvention = CallingConvention.Cdecl)] [return: MarshalAs(UnmanagedType.I1)]
  public static extern bool SteamAPI_ISteamUtils_GetAPICallResult(IntPtr self, ulong call, [Out] byte[] buf, int cub, int expected, [MarshalAs(UnmanagedType.I1)] out bool failed);
}
"@

  $err = New-Object byte[] 1024
  $init = [CzSteam]::SteamAPI_InitFlat($err)
  if ($init -ne 0) {
    $msg = [Text.Encoding]::UTF8.GetString($err).Trim([char]0)
    Finish $false "Steam API didn't start ($init): $msg. Is Steam running and logged in?"
  }
  $initialized = $true
  $utils = [CzSteam]::SteamAPI_SteamUtils_v010()
  $storage = [CzSteam]::SteamAPI_SteamRemoteStorage_v016()
  if ($utils -eq [IntPtr]::Zero -or $storage -eq [IntPtr]::Zero) { Finish $false "Steam API interfaces unavailable" }
  $user = [CzSteam]::SteamAPI_SteamUser_v023()
  $steamId = [CzSteam]::SteamAPI_ISteamUser_GetSteamID($user)
  $app = [CzSteam]::SteamAPI_ISteamUtils_GetAppID($utils)
  if ($app -ne $TtsApp) { Finish $false "Steam API started as app $app, not TTS ($TtsApp)" @{ steam_id = "$steamId" } }
  # Init can return before the game has a live server connection. Give Steam
  # time to authenticate before touching its cloud or committing the update.
  $connectDeadline = (Get-Date).AddSeconds(60)
  while (-not [CzSteam]::SteamAPI_ISteamUser_BLoggedOn($user)) {
    if ((Get-Date) -gt $connectDeadline) {
      Finish $false "Uploader's Steam session is not connected. Close SteamCMD and reconnect/restart desktop Steam, then retry." @{ steam_id = "$steamId"; eresult = 21; item = "$Item" }
    }
    [CzSteam]::SteamAPI_RunCallbacks()
    Start-Sleep -Milliseconds 200
  }

  foreach ($pair in @(@($CloudFile, $File), @($CloudPreview, $Preview))) {
    $bytes = [IO.File]::ReadAllBytes($pair[1])
    if (-not [CzSteam]::SteamAPI_ISteamRemoteStorage_FileWrite($storage, $pair[0], $bytes, $bytes.Length)) {
      Finish $false "couldn't write $($pair[0]) to TTS's Steam Cloud (quota?)" @{ steam_id = "$steamId" }
    }
  }

  $h = [CzSteam]::SteamAPI_ISteamRemoteStorage_CreatePublishedFileUpdateRequest($storage, $Item)
  if ($h -eq 0 -or $h -eq [UInt64]::MaxValue) { Finish $false "Steam refused the update handle" @{ steam_id = "$steamId" } }
  $set = [CzSteam]::SteamAPI_ISteamRemoteStorage_UpdatePublishedFileFile($storage, $h, $CloudFile) -and
         [CzSteam]::SteamAPI_ISteamRemoteStorage_UpdatePublishedFilePreviewFile($storage, $h, $CloudPreview)
  if ($Note) { $set = $set -and [CzSteam]::SteamAPI_ISteamRemoteStorage_UpdatePublishedFileSetChangeDescription($storage, $h, $Note) }
  if (-not $set) { Finish $false "Steam refused the update request" @{ steam_id = "$steamId" } }
  $call = [CzSteam]::SteamAPI_ISteamRemoteStorage_CommitPublishedFileUpdate($storage, $h)
  if ($call -eq 0) { Finish $false "Steam refused to start the update" @{ steam_id = "$steamId" } }

  # RemoteStorageUpdatePublishedFileResult_t (callback 1316): EResult at 0, the item id at 8,
  # "needs to accept the Workshop agreement" at 16; 24 bytes with Steam's 8-byte packing.
  $failed = $false
  $deadline = (Get-Date).AddMinutes(10)
  while (-not [CzSteam]::SteamAPI_ISteamUtils_IsAPICallCompleted($utils, $call, [ref]$failed)) {
    if ((Get-Date) -gt $deadline) { Finish $false "Steam didn't answer within 10 minutes" @{ steam_id = "$steamId" } }
    [CzSteam]::SteamAPI_RunCallbacks()
    Start-Sleep -Milliseconds 200
  }
  $buf = New-Object byte[] 24
  $got = [CzSteam]::SteamAPI_ISteamUtils_GetAPICallResult($utils, $call, $buf, 24, 1316, [ref]$failed)
  $eresult = [BitConverter]::ToInt32($buf, 0)
  $id = [BitConverter]::ToUInt64($buf, 8)
  $legal = $buf[16] -ne 0
  $extra = @{ eresult = $eresult; item = "$id"; steam_id = "$steamId"; needs_legal_agreement = $legal }
  if ($got -and -not $failed -and $eresult -eq 1 -and $id -eq $Item -and -not $legal) { Finish $true "updated" $extra }
  Finish $false "Steam answered EResult $eresult (1 = OK; 15 = access denied; 21 = not logged on)" $extra
} catch {
  Finish $false "uploader crashed: $($_.Exception.Message)"
} finally {
  if ($initialized) { [CzSteam]::SteamAPI_Shutdown() }
}
