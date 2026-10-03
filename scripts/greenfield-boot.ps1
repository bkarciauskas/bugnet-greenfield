# Boot script for the greenfield site on port 8080.
# User-data replaces the __TOKEN__ placeholders with single-use presigned URLs.
# It does not change the site on port 80 and it does not create a shutdown task.
$ErrorActionPreference = "Stop"
$log = "C:\migrate\greenfield-setup.log"
New-Item -ItemType Directory -Force -Path C:\migrate, C:\migrate\markers, C:\EmailGreenfield | Out-Null

function Write-Log([string]$message) {
    $line = (Get-Date).ToUniversalTime().ToString("o") + " " + $message
    Add-Content -Path $log -Value $line
    try {
        Invoke-WebRequest -Uri "__LOG_PUT__" -Method Put -InFile $log -UseBasicParsing | Out-Null
    } catch {
        Add-Content -Path $log -Value ((Get-Date).ToUniversalTime().ToString("o") + " log upload failed")
    }
}

Write-Log "greenfield boot start"
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

$instance = "localhost\SQLEXPRESS"
$probe = & $sqlcmd -S $instance -E -Q "SELECT 1" -b -h -1 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Log "sql express probe failed"
    exit 1
}

$db = & $sqlcmd -S $instance -E -Q "SET NOCOUNT ON; SELECT DB_ID(N'BugNetGreenfield')" -h -1 -W
if ($db -match "NULL" -or [string]::IsNullOrWhiteSpace($db)) {
    Write-Log "copying BugNET into BugNetGreenfield"
    & $sqlcmd -S $instance -E -Q "BACKUP DATABASE [BugNET] TO DISK = N'C:\migrate\bugnet-green.bak' WITH COPY_ONLY, INIT" -b
    if ($LASTEXITCODE -ne 0) { Write-Log "backup failed"; exit 1 }
    $files = & $sqlcmd -S $instance -E -Q "SET NOCOUNT ON; RESTORE FILELISTONLY FROM DISK = N'C:\migrate\bugnet-green.bak'" -s "|" -W -h -1
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
    & $sqlcmd -S $instance -E -Q $restore -b
    if ($LASTEXITCODE -ne 0) { Write-Log "restore failed"; exit 1 }
    Write-Log "database restored"
} else {
    Write-Log "database already present"
}

if (-not (Test-Path "C:\migrate\markers\dotnet-hosting-8.done")) {
    Write-Log "installing asp.net core 8 hosting bundle"
    $installer = "C:\migrate\dotnet-hosting-8.exe"
    Invoke-WebRequest -Uri "https://aka.ms/dotnet/8.0/dotnet-hosting-win.exe" -OutFile $installer -UseBasicParsing
    $proc = Start-Process -FilePath $installer -ArgumentList "/quiet","/norestart" -Wait -PassThru
    if ($proc.ExitCode -eq 3010) {
        New-Item -ItemType File -Force -Path "C:\migrate\markers\dotnet-hosting-8.done" | Out-Null
        Write-Log "hosting bundle requested reboot"
        shutdown.exe /r /t 15 /f
        exit 0
    }
    if ($proc.ExitCode -ne 0) {
        Write-Log ("hosting bundle exit " + $proc.ExitCode)
        exit 1
    }
    New-Item -ItemType File -Force -Path "C:\migrate\markers\dotnet-hosting-8.done" | Out-Null
    Write-Log "hosting bundle installed"
}

Write-Log "downloading site"
Invoke-WebRequest -Uri "__APP_GET__" -OutFile "C:\migrate\bugnet-greenfield.zip" -UseBasicParsing
if (Test-Path $sitePath) { Remove-Item $sitePath -Recurse -Force }
Expand-Archive -Path "C:\migrate\bugnet-greenfield.zip" -DestinationPath $sitePath -Force
@"
{
  "ConnectionStrings": {
    "BugNet": "Server=localhost\\SQLEXPRESS;Database=BugNetGreenfield;Trusted_Connection=True;TrustServerCertificate=True"
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
& $sqlcmd -S $instance -E -Q "IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = N'$login') CREATE LOGIN [$login] FROM WINDOWS;" -b
& $sqlcmd -S $instance -E -d BugNetGreenfield -Q "IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = N'$login') CREATE USER [$login] FOR LOGIN [$login]; ALTER ROLE db_owner ADD MEMBER [$login];" -b
if (-not (Get-Website -Name $siteName -ErrorAction SilentlyContinue)) {
    New-Website -Name $siteName -Port 8080 -PhysicalPath $sitePath -ApplicationPool $poolName | Out-Null
} else {
    Set-ItemProperty "IIS:\Sites\$siteName" physicalPath $sitePath
}
$acl = Get-Acl "C:\EmailGreenfield"
$rule = New-Object System.Security.AccessControl.FileSystemAccessRule($login, "Modify", "ContainerInherit,ObjectInherit", "None", "Allow")
$acl.SetAccessRule($rule)
Set-Acl "C:\EmailGreenfield" $acl
Start-Website -Name $siteName
Write-Log "site started on 8080"

$uploader = @'
$ErrorActionPreference = "Stop"
$dir = "C:\EmailGreenfield"
$listPath = "C:\migrate\mail-new-put-urls.txt"
$usedPath = "C:\migrate\mail-new-used.txt"
Invoke-WebRequest -Uri "__MAIL_LIST_GET__" -OutFile $listPath -UseBasicParsing
$used = @{}
if (Test-Path $usedPath) {
    Get-Content $usedPath | ForEach-Object { if ($_) { $used[$_] = $true } }
}
$free = @(Get-Content $listPath | Where-Object { $_ -and -not $used.ContainsKey($_) })
if ($free.Count -lt 10) {
    try { Invoke-WebRequest -Uri "__STATUS_PUT__" -Method Put -Body "slots-low $($free.Count)" -UseBasicParsing | Out-Null } catch {}
}
Get-ChildItem $dir -Filter *.eml | Sort-Object LastWriteTime | ForEach-Object {
    if ($free.Count -eq 0) { return }
    $url = $free[0]
    if ($free.Count -eq 1) { $free = @() } else { $free = @($free | Select-Object -Skip 1) }
    Invoke-WebRequest -Uri $url -Method Put -InFile $_.FullName -ContentType "message/rfc822" -UseBasicParsing | Out-Null
    Add-Content $usedPath $url
    Remove-Item $_.FullName -Force
}
'@
Set-Content -Path "C:\migrate\mail-new-upload.ps1" -Value $uploader -Encoding ascii
$task = Get-ScheduledTask -TaskName "bugnet-mail-capture-greenfield" -ErrorAction SilentlyContinue
if (-not $task) {
    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File C:\migrate\mail-new-upload.ps1"
    $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 1) -RepetitionDuration (New-TimeSpan -Days 9999)
    Register-ScheduledTask -TaskName "bugnet-mail-capture-greenfield" -Action $action -Trigger $trigger -User "SYSTEM" -RunLevel Highest | Out-Null
}
Write-Log "greenfield boot done"
