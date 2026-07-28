[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$PptxPath,

    [Parameter(Mandatory = $true)]
    [string]$OutputDir,

    [Parameter(Mandatory = $true)]
    [ValidateRange(36, 600)]
    [int]$Dpi
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $PptxPath -PathType Leaf)) {
    throw "PPTX file not found: $PptxPath"
}
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$powerpoint = $null
$presentation = $null
try {
    $powerpoint = New-Object -ComObject PowerPoint.Application
    # PowerPoint expects MsoTriState here, not a PowerShell Boolean.
    # PowerPoint refuses to hide the application while exporting. The
    # presentation itself is opened without a window below.
    $powerpoint.Visible = [int32]-1
    try {
        $presentation = $powerpoint.Presentations.Open(
            $PptxPath,
            [int32]-1,
            [int32]0,
            [int32]0
        )
    }
    catch [System.Runtime.InteropServices.COMException] {
        # Some Microsoft 365 builds reject an otherwise valid package when
        # WithWindow=msoFalse and the deck contains embedded media. Retry with
        # a real (minimized) presentation window before treating the PPTX as
        # corrupt. Pure-vector decks continue to use the headless path.
        try { $powerpoint.Quit() } catch { }
        $powerpoint = New-Object -ComObject PowerPoint.Application
        $powerpoint.Visible = [int32]-1
        $presentation = $powerpoint.Presentations.Open(
            $PptxPath,
            [int32]-1,
            [int32]0,
            [int32]-1
        )
        try { $powerpoint.WindowState = [int32]2 } catch { }
    }

    $slideWidth = [double]$presentation.PageSetup.SlideWidth
    $slideHeight = [double]$presentation.PageSetup.SlideHeight
    $widthPixels = [int][Math]::Round(($slideWidth / 72.0) * $Dpi)
    $heightPixels = [int][Math]::Round(($slideHeight / 72.0) * $Dpi)
    $presentation.Export($OutputDir, "PNG", $widthPixels, $heightPixels)

    # The filename is localized by Office (for example, 幻灯片1.PNG in a
    # Chinese installation), so only the PNG extension is authoritative.
    $slides = @(Get-ChildItem -LiteralPath $OutputDir -File | Where-Object { $_.Extension -ieq '.png' })
    if ($slides.Count -eq 0) {
        throw "PowerPoint did not export any slide PNG files."
    }
}
finally {
    if ($null -ne $presentation) {
        try { $presentation.Close() } catch { }
    }
    if ($null -ne $powerpoint) {
        try { $powerpoint.Quit() } catch { }
    }
}
