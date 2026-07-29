param(
  [Parameter(Mandatory = $true)]
  [string]$Executable,
  [string[]]$Arguments = @(),
  [Parameter(Mandatory = $true)]
  [string]$Output
)

$ErrorActionPreference = "Stop"
$probeRoot = Join-Path $env:TEMP "SimpleCast-frame-probe"
New-Item -ItemType Directory -Force -Path `
  (Join-Path $probeRoot "Roaming"), `
  (Join-Path $probeRoot "Local") | Out-Null
$env:APPDATA = Join-Path $probeRoot "Roaming"
$env:LOCALAPPDATA = Join-Path $probeRoot "Local"

Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;

public static class SimpleCastFrameProbe {
    public delegate bool EnumWindowsProc(IntPtr hwnd, IntPtr lParam);

    [StructLayout(LayoutKind.Sequential)]
    public struct RECT {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr hwnd, out RECT rect);

    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hwnd);

    [DllImport("user32.dll")]
    public static extern bool EnumWindows(EnumWindowsProc callback, IntPtr lParam);

    [DllImport("user32.dll")]
    public static extern uint GetWindowThreadProcessId(
        IntPtr hwnd,
        out uint processId
    );

    [DllImport("user32.dll")]
    public static extern bool IsWindowVisible(IntPtr hwnd);

    [DllImport("user32.dll")]
    public static extern bool PostMessage(
        IntPtr hwnd,
        uint message,
        IntPtr wParam,
        IntPtr lParam
    );

    [DllImport("user32.dll")]
    public static extern IntPtr GetWindowLongPtr(IntPtr hwnd, int index);

    [DllImport("dwmapi.dll")]
    public static extern int DwmGetWindowAttribute(
        IntPtr hwnd,
        uint attribute,
        out uint value,
        uint valueSize
    );

    public static IntPtr FindVisibleWindow(uint wantedProcessId) {
        IntPtr found = IntPtr.Zero;
        EnumWindows(delegate (IntPtr hwnd, IntPtr lParam) {
            uint processId;
            GetWindowThreadProcessId(hwnd, out processId);
            if (processId == wantedProcessId && IsWindowVisible(hwnd)) {
                found = hwnd;
                return false;
            }
            return true;
        }, IntPtr.Zero);
        return found;
    }
}
"@

$process = Start-Process `
  -FilePath $Executable `
  -ArgumentList $Arguments `
  -PassThru
try {
  $process.WaitForInputIdle(10000) | Out-Null
  Start-Sleep -Seconds 3
  $process.Refresh()
  $windowHandle = $process.MainWindowHandle
  if ($windowHandle -eq [IntPtr]::Zero) {
    $windowHandle = [SimpleCastFrameProbe]::FindVisibleWindow($process.Id)
  }
  if ($windowHandle -eq [IntPtr]::Zero) {
    throw "SimpleCast did not create a main window."
  }
  [SimpleCastFrameProbe]::SetForegroundWindow($windowHandle) |
    Out-Null
  Start-Sleep -Milliseconds 500
  $rect = New-Object SimpleCastFrameProbe+RECT
  if (-not [SimpleCastFrameProbe]::GetWindowRect(
    $windowHandle,
    [ref]$rect
  )) {
    throw "Could not read the SimpleCast window rectangle."
  }
  $width = $rect.Right - $rect.Left
  $height = $rect.Bottom - $rect.Top
  $borderColor = 0
  $borderResult = [SimpleCastFrameProbe]::DwmGetWindowAttribute(
    $windowHandle,
    34,
    [ref]$borderColor,
    4
  )
  $windowStyle = [SimpleCastFrameProbe]::GetWindowLongPtr(
    $windowHandle,
    -16
  ).ToInt64()
  $bitmap = New-Object System.Drawing.Bitmap $width, $height
  $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
  try {
    $graphics.CopyFromScreen(
      $rect.Left,
      $rect.Top,
      0,
      0,
      (New-Object System.Drawing.Size $width, $height)
    )
    $bitmap.Save($Output, [System.Drawing.Imaging.ImageFormat]::Png)
  } finally {
    $graphics.Dispose()
    $bitmap.Dispose()
  }
  [pscustomobject]@{
    Handle = $windowHandle
    Left = $rect.Left
    Top = $rect.Top
    Width = $width
    Height = $height
    WindowStyle = "0x{0:X8}" -f $windowStyle
    DwmBorderResult = $borderResult
    DwmBorderColor = "0x{0:X8}" -f $borderColor
    Output = $Output
  } | Format-List
} finally {
  if (-not $process.HasExited) {
    if ($windowHandle -ne [IntPtr]::Zero) {
      [SimpleCastFrameProbe]::PostMessage(
        $windowHandle,
        0x0010,
        [IntPtr]::Zero,
        [IntPtr]::Zero
      ) | Out-Null
    } else {
      $process.CloseMainWindow() | Out-Null
    }
    if (-not $process.WaitForExit(10000)) {
      Stop-Process -Id $process.Id -Force
    }
  }
}
