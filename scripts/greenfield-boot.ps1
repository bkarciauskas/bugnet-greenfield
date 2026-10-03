# Boot script for the greenfield site on port 8080.
# User-data replaces the __TOKEN__ placeholders with single-use presigned URLs.
# It does not change the site on port 80 and it does not create a shutdown task.
$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$log = "C:\migrate\greenfield-setup.log"
New-Item -ItemType Directory -Force -Path C:\migrate, C:\migrate\markers, C:\EmailGreenfield | Out-Null

function Write-Log([string]$message) {
    $line = (Get-Date).ToUniversalTime().ToString("o") + " " + $message
    Add-Content -Path $log -Value $line
    curl.exe -sS --max-time 30 -X PUT --upload-file $log "__LOG_PUT__" -o NUL
}

function Invoke-Sql([string[]]$ArgumentList) {
    $start = New-Object System.Diagnostics.ProcessStartInfo
    $start.FileName = $sqlcmd
    $quoted = foreach ($arg in $ArgumentList) {
        if ($arg -match '^[A-Za-z0-9_./:\\-]+$') { $arg } else { '"' + ($arg -replace '"', '\"') + '"' }
    }
    $start.Arguments = $quoted -join ' '
    $start.UseShellExecute = $false
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    $start.CreateNoWindow = $true
    $proc = New-Object System.Diagnostics.Process
    $proc.StartInfo = $start
    [void]$proc.Start()
    $outTask = $proc.StandardOutput.ReadToEndAsync()
    $errTask = $proc.StandardError.ReadToEndAsync()
    $proc.WaitForExit()
    return [pscustomobject]@{ Code = $proc.ExitCode; Out = $outTask.Result; Err = $errTask.Result }
}

if (-not (Get-NetFirewallRule -DisplayName "BugNetGreenfield-8080" -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName "BugNetGreenfield-8080" -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow | Out-Null
}
$progressListener = $null
try {
    $progressListener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Any, 8080)
    $progressListener.Start()
    $progressShell = [powershell]::Create()
    $progressShell.Runspace = [runspacefactory]::CreateRunspace()
    $progressShell.Runspace.Open()
    [void]$progressShell.AddScript({
        param($listener, $logPath)
        while ($true) {
            if (-not $listener.Pending()) { Start-Sleep -Milliseconds 200; continue }
            $client = $listener.AcceptTcpClient()
            try {
                $text = "starting"
                if (Test-Path $logPath) { $text = (Get-Content $logPath -Tail 12) -join "`n" }
                $body = [Text.Encoding]::ASCII.GetBytes($text)
                $header = [Text.Encoding]::ASCII.GetBytes("HTTP/1.1 200 OK`r`nContent-Type: text/plain`r`nContent-Length: $($body.Length)`r`nConnection: close`r`n`r`n")
                $stream = $client.GetStream()
                $stream.Write($header, 0, $header.Length)
                $stream.Write($body, 0, $body.Length)
                $stream.Flush()
            } finally {
                $client.Close()
            }
        }
    }).AddArgument($progressListener).AddArgument($log)
    $progressHandle = $progressShell.BeginInvoke()
} catch {
    Add-Content -Path $log -Value ((Get-Date).ToUniversalTime().ToString("o") + " progress listener failed")
}

Write-Log "greenfield boot start"
Write-Log ("identity " + [Security.Principal.WindowsIdentity]::GetCurrent().Name)
$siteName = "BugNetGreenfield"
$sitePath = "C:\inetpub\bugnet-greenfield"
$poolName = "BugNetGreenfield"

$sqlcmd = Get-Command sqlcmd -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source
if (-not $sqlcmd) {
    $sqlcmd = Get-ChildItem "C:\Program Files\Microsoft SQL Server" -Recurse -Filter sqlcmd.exe -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
}
if (-not $sqlcmd) {
    Write-Log "sqlcmd missing"
    exit 1
}

$instance = $null
$probe = $null
foreach ($candidate in @("lpc:.\SQLEXPRESS", ".\SQLEXPRESS", "localhost\SQLEXPRESS", "lpc:.", "localhost")) {
    foreach ($try in 1..3) {
        $probe = Invoke-Sql @("-S", $candidate, "-E", "-Q", "SELECT 1", "-b", "-h", "-1", "-l", "5")
        if ($probe.Code -eq 0) { $instance = $candidate; break }
        $detail = (($probe.Err + " " + $probe.Out) -replace '\s+', ' ').Trim()
        if ($detail.Length -gt 220) { $detail = $detail.Substring(0, 220) }
        Write-Log ("sql candidate " + $candidate + " try " + $try + " exit " + $probe.Code + " " + $detail)
        Start-Sleep -Seconds 5
    }
    if ($instance) { break }
}
if (-not $instance) {
    Write-Log "sql express probe failed"
    exit 1
}
Write-Log ("sql server " + $instance)

$dbResult = Invoke-Sql @("-S", $instance, "-E", "-Q", "SET NOCOUNT ON; SELECT DB_ID(N'BugNetGreenfield')", "-h", "-1", "-W")
$db = $dbResult.Out
if ($db -match "NULL" -or [string]::IsNullOrWhiteSpace($db)) {
    Write-Log "copying BugNET into BugNetGreenfield"
    $backup = Invoke-Sql @("-S", $instance, "-E", "-Q", "BACKUP DATABASE [BugNET] TO DISK = N'C:\migrate\bugnet-green.bak' WITH COPY_ONLY, INIT", "-b")
    if ($backup.Code -ne 0) { Write-Log "backup failed"; exit 1 }
    $fileResult = Invoke-Sql @("-S", $instance, "-E", "-Q", "SET NOCOUNT ON; RESTORE FILELISTONLY FROM DISK = N'C:\migrate\bugnet-green.bak'", "-s", "|", "-W", "-h", "-1")
    $files = $fileResult.Out -split "`r?`n"
    $moves = @()
    foreach ($row in $files) {
        $parts = $row.Split("|")
        if ($parts.Length -lt 3) { continue }
        $logical = $parts[0].Trim()
        $physical = $parts[1].Trim()
        if ([string]::IsNullOrWhiteSpace($logical) -or $logical -eq "LogicalName") { continue }
        $leaf = [IO.Path]::GetFileName($physical)
        $dest = "C:\migrate\greenfield-$leaf"
        $moves += "MOVE N'$logical' TO N'$dest'"
    }
    $restore = "RESTORE DATABASE [BugNetGreenfield] FROM DISK = N'C:\migrate\bugnet-green.bak' WITH " + ($moves -join ", ")
    $restored = Invoke-Sql @("-S", $instance, "-E", "-Q", $restore, "-b")
    if ($restored.Code -ne 0) { Write-Log "restore failed"; exit 1 }
    Write-Log "database restored"
} else {
    Write-Log "database already present"
}

if (-not (Test-Path "C:\migrate\markers\dotnet-hosting-8.done")) {
    Write-Log "installing asp.net core 8 hosting bundle"
    $installer = "C:\migrate\dotnet-hosting-8.exe"
    curl.exe -sS -L "https://aka.ms/dotnet/8.0/dotnet-hosting-win.exe" -o $installer
    $proc = Start-Process -FilePath $installer -ArgumentList "/quiet","/norestart" -Wait -PassThru
    if ($proc.ExitCode -eq 3010) {
        New-Item -ItemType File -Force -Path "C:\migrate\markers\dotnet-hosting-8.done" | Out-Null
        Write-Log "hosting bundle requested reboot"
        exit 3010
    }
    if ($proc.ExitCode -ne 0) {
        Write-Log ("hosting bundle exit " + $proc.ExitCode)
        exit 1
    }
    New-Item -ItemType File -Force -Path "C:\migrate\markers\dotnet-hosting-8.done" | Out-Null
    Write-Log "hosting bundle installed"
}

Write-Log "downloading site"
curl.exe -sS -L "__APP_GET__" -o "C:\migrate\bugnet-greenfield.zip"
if (Test-Path $sitePath) { Remove-Item $sitePath -Recurse -Force }
Expand-Archive -Path "C:\migrate\bugnet-greenfield.zip" -DestinationPath $sitePath -Force
$webConfigPath = Join-Path $sitePath "web.config"
$webConfig = Get-Content $webConfigPath -Raw
$dotnet = "C:\Program Files\dotnet\dotnet.exe"
$webConfig = $webConfig.Replace('processPath="dotnet"', "processPath=`"$dotnet`"")
Set-Content -Path $webConfigPath -Value $webConfig -Encoding ascii
$sqlServer = $instance.Replace("\", "\\")
@"
{
  "ConnectionStrings": {
    "BugNet": "Server=$sqlServer;Database=BugNetGreenfield;Trusted_Connection=True;TrustServerCertificate=True"
  },
  "Mail": {
    "PickupDirectory": "C:\\EmailGreenfield"
  }
}
"@ | Set-Content -Path (Join-Path $sitePath "appsettings.Production.json") -Encoding ascii

Import-Module WebAdministration
if (-not (Test-Path "IIS:\AppPools\$poolName")) {
    New-WebAppPool $poolName | Out-Null
    Set-ItemProperty "IIS:\AppPools\$poolName" managedRuntimeVersion ""
}
$login = "IIS APPPOOL\$poolName"
$serverLogin = Invoke-Sql @("-S", $instance, "-E", "-Q", "IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = N'$login') CREATE LOGIN [$login] FROM WINDOWS;", "-b")
Write-Log ("app pool server login " + $serverLogin.Code)
$dbLogin = Invoke-Sql @("-S", $instance, "-E", "-d", "BugNetGreenfield", "-Q", "IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = N'$login') CREATE USER [$login] FOR LOGIN [$login]; ALTER ROLE db_owner ADD MEMBER [$login];", "-b")
Write-Log ("app pool database login " + $dbLogin.Code)
if (-not (Get-Website -Name $siteName -ErrorAction SilentlyContinue)) {
    New-Website -Name $siteName -Port 8080 -PhysicalPath $sitePath -ApplicationPool $poolName | Out-Null
} else {
    Set-ItemProperty "IIS:\Sites\$siteName" physicalPath $sitePath
}
$acl = Get-Acl "C:\EmailGreenfield"
$rule = New-Object System.Security.AccessControl.FileSystemAccessRule($login, "Modify", "ContainerInherit,ObjectInherit", "None", "Allow")
$acl.SetAccessRule($rule)
Set-Acl "C:\EmailGreenfield" $acl
if ($progressListener) { $progressListener.Stop() }
Start-Sleep -Seconds 2
Start-Website -Name $siteName
Restart-WebAppPool -Name $poolName
Write-Log "site started on 8080"
Start-Sleep -Seconds 3
try {
    $probe = Invoke-WebRequest -Uri "http://127.0.0.1:8080/" -UseBasicParsing -MaximumRedirection 0 -ErrorAction Stop
    Write-Log ("local probe " + [int]$probe.StatusCode)
} catch {
    $response = $_.Exception.Response
    if ($response) {
        Write-Log ("local probe " + [int]$response.StatusCode)
    } else {
        Write-Log ("local probe failed " + $_.Exception.Message)
    }
}

$uploader = @'
$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$dir = "C:\EmailGreenfield"
$listPath = "C:\migrate\mail-new-put-urls.txt"
$usedPath = "C:\migrate\mail-new-used.txt"
curl.exe -sS -L "__MAIL_LIST_GET__" -o $listPath
$used = @{}
if (Test-Path $usedPath) {
    Get-Content $usedPath | ForEach-Object { if ($_) { $used[$_] = $true } }
}
$free = @(Get-Content $listPath | Where-Object { $_ -and -not $used.ContainsKey($_) })
if ($free.Count -lt 10) {
    try { curl.exe -sS -X PUT -d "slots-low $($free.Count)" "__STATUS_PUT__" -o NUL } catch {}
}
Get-ChildItem $dir -Filter *.eml | Sort-Object LastWriteTime | ForEach-Object {
    if ($free.Count -eq 0) { return }
    $url = $free[0]
    if ($free.Count -eq 1) { $free = @() } else { $free = @($free | Select-Object -Skip 1) }
    curl.exe -sS -X PUT --upload-file $_.FullName -H "Content-Type: message/rfc822" "$url" -o NUL
    Add-Content $usedPath $url
    Remove-Item $_.FullName -Force
}
'@
Set-Content -Path "C:\migrate\mail-new-upload.ps1" -Value $uploader -Encoding ascii
try {
    $task = Get-ScheduledTask -TaskName "bugnet-mail-capture-greenfield" -ErrorAction SilentlyContinue
    if (-not $task) {
        $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File C:\migrate\mail-new-upload.ps1"
        $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 1) -RepetitionDuration (New-TimeSpan -Days 30)
        Register-ScheduledTask -TaskName "bugnet-mail-capture-greenfield" -Action $action -Trigger $trigger -User "SYSTEM" -RunLevel Highest | Out-Null
        Write-Log "mail task registered"
    } else {
        Write-Log "mail task already present"
    }
} catch {
    Write-Log ("mail task failed " + $_.Exception.Message)
}
Write-Log "greenfield boot done"
