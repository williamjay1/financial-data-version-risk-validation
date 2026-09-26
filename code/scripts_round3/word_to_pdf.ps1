# Convert a Word document to PDF through the installed Word automation server.
# The export is the operation that matters; a failed Quit afterwards is reported
# but not treated as an export failure, because Word sometimes drops the
# automation channel while shutting down.
param(
  [Parameter(Mandatory = $true)][string]$Docx,
  [Parameter(Mandatory = $true)][string]$Pdf
)
$ErrorActionPreference = 'Stop'
if (Test-Path $Pdf) { Remove-Item $Pdf -Force }
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$exported = $false
try {
  $doc = $word.Documents.Open($Docx, $false, $true)
  $doc.ExportAsFixedFormat($Pdf, 17)
  $exported = Test-Path $Pdf
  try { $doc.Close($false) } catch { }
}
finally {
  try { $word.Quit() } catch { }
}
if (-not $exported) { throw "Word export produced no PDF for $Docx" }
Write-Output "OK $Pdf"
