$ErrorActionPreference = 'Continue'
$bin = 'C:\Program Files (x86)cv8\8.3.27.1936incv8.exe'
$out = 'C:С-Framework	mp\MCP_Server_from_mfm.cfe'
$log = 'C:С-Framework	mp\dumpcfe.log'
$args = @('DESIGNER','/S','DESKTOP-TNU600C°507_DEV_ATERLETSKIY_53196','/N','Администратор','/P','','/DumpCfg',$out,'-Extension','MCP_Сервер','/Out',$log,'/DisableStartupMessages')
$p = Start-Process -FilePath $bin -ArgumentList $args -Wait -PassThru -NoNewWindow
Write-Output ("EXIT=" + $p.ExitCode)
if (Test-Path $out) { Write-Output ("SIZE=" + (Get-Item $out).Length) } else { Write-Output "NO FILE" }
if (Test-Path $log) { Get-Content $log -Encoding UTF8 | Select-Object -First 5 }
