# Export Mermaid diagrams to PNG for PDF / Word embedding.
# Requires: npm install -g @mermaid-js/mermaid-cli

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Diagrams = Join-Path $Root "docs\diagrams"
$Images = Join-Path $Root "docs\images"

if (-not (Get-Command mmdc -ErrorAction SilentlyContinue)) {
    Write-Host "mmdc not found. Install with: npm install -g @mermaid-js/mermaid-cli"
    exit 1
}

New-Item -ItemType Directory -Force -Path $Images | Out-Null

Get-ChildItem $Diagrams -Filter "*.mmd" | ForEach-Object {
    $out = Join-Path $Images ($_.BaseName + ".png")
    Write-Host "Rendering $($_.Name) -> $out"
    mmdc -i $_.FullName -o $out -b white -w 1200
}

Write-Host "Done. Images in docs/images/"
Write-Host "Embed in README or docs/PDF-AND-DIAGRAMS.md, then export to PDF."
