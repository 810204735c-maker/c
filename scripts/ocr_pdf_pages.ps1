param(
    [Parameter(Mandatory = $true)][string]$ImageDirectory,
    [Parameter(Mandatory = $true)][string]$OutputDirectory,
    [int]$StartPage = 1,
    [int]$EndPage = 207
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Foundation.IAsyncOperation`1, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.SoftwareBitmap, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Storage.Streams.RandomAccessStream, Windows.Storage.Streams, ContentType = WindowsRuntime]
$null = [Windows.Globalization.Language, Windows.Foundation, ContentType = WindowsRuntime]
$language = [Windows.Globalization.Language]::new('zh-Hans-CN')
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($language)
if (-not $engine) { throw 'Chinese Windows OCR language pack is unavailable.' }
$awaiterMethod = [WindowsRuntimeSystemExtensions].GetMember('GetAwaiter') |
    Where-Object { $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' } |
    Select-Object -First 1
function Await-Operation($Operation, $ResultType) {
    $awaiterMethod.MakeGenericMethod($ResultType).Invoke($null, @($Operation)).GetResult()
}
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
for ($page = $StartPage; $page -le $EndPage; $page++) {
    $inputPath = Join-Path $ImageDirectory ('page-{0:d3}.jpg' -f $page)
    $outputPath = Join-Path $OutputDirectory ('page-{0:d3}.txt' -f $page)
    if (Test-Path -LiteralPath $outputPath) { continue }
    $fileStream = [System.IO.File]::OpenRead($inputPath)
    $stream = [System.IO.WindowsRuntimeStreamExtensions]::AsRandomAccessStream($fileStream)
    $decoder = Await-Operation ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $bitmap = Await-Operation ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
    $result = Await-Operation ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
    $lines = @($result.Lines | ForEach-Object { $_.Text })
    [System.IO.File]::WriteAllLines($outputPath, $lines, [System.Text.UTF8Encoding]::new($false))
    $bitmap.Dispose()
    $stream.Dispose()
    $fileStream.Dispose()
    Write-Output ('{0}: {1} chars' -f $page, $result.Text.Length)
}
