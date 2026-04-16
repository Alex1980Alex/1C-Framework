$vrdPath = "C:\inetpub\wwwroot\DEV_ATERLETSKIY_39144_MFM\default.vrd"
$c = Get-Content $vrdPath -Raw
$c = $c.Replace('<standardOdata enable="false"', "<httpServices publishExtensionsByDefault=`"true`"/>`r`n`t<standardOdata enable=`"false`"")
Set-Content $vrdPath -Value $c -Encoding UTF8
Write-Host "DONE"
