$files = @("test_enrichment.py", "test_ws_debug.py", "test_ws_content.py", "test_prompt.py", "test_prompt.ps1")
foreach ($f in $files) {
    $path = "d:\1С-Framework\$f"
    if (Test-Path $path) {
        Remove-Item $path -Force
        Write-Output "Deleted: $f"
    }
}
# Self-delete
Remove-Item "d:\1С-Framework\cleanup.ps1" -Force
