$ErrorActionPreference = 'Stop'
$processes = @(Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'python|uv.exe' } | ForEach-Object {
    [pscustomobject]@{pid=$_.ProcessId; parent=$_.ParentProcessId; name=$_.Name;
        repo_match=($_.CommandLine -like '*Echomind_new*' -or $_.ExecutablePath -like '*Echomind_new*');
        api_match=($_.CommandLine -match 'api.main|uvicorn');
        writer_match=($_.CommandLine -match 'seed_demo_knowledge|default_kb_publication|rag_quality|demo.prepare')}
})
$listeners = @(Get-NetTCPConnection -State Listen | Where-Object { $_.LocalPort -in 8000,8001,8080 } | Select-Object LocalAddress,LocalPort,OwningProcess)
$connections = @(Get-NetTCPConnection -State Established | Where-Object { $_.LocalPort -eq 8001 } | Select-Object LocalAddress,RemoteAddress,RemotePort,OwningProcess)
$appState = (& docker inspect echomind-app --format '{{json .State}}' | ConvertFrom-Json)
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect local CartCare API' }
$chromaLabels = (& docker inspect echomind-chromadb --format '{{json .Config.Labels}}' | ConvertFrom-Json)
$bindings = (& docker inspect echomind-chromadb --format '{{json .HostConfig.PortBindings}}' | ConvertFrom-Json)
$mounts = (& docker inspect echomind-chromadb --format '{{json .Mounts}}' | ConvertFrom-Json)
$chromaState = (& docker inspect echomind-chromadb --format '{{json .State}}' | ConvertFrom-Json)
$running = @(& docker ps --format '{{.Names}}')
$wslState = ((& wsl --list --verbose) -join "`n").Replace([string][char]0,'')
$context = (& docker context inspect desktop-linux --format '{{json .Endpoints.docker.Host}}' | ConvertFrom-Json)
$serverProcesses = @(& docker top echomind-chromadb -eo pid,comm)
if ($appState.Running -or ($listeners | Where-Object { $_.LocalPort -in 8000,8080 }) -or ($processes | Where-Object { $_.api_match -or $_.writer_match })) { throw 'API/writer is still active' }
if ($connections.Count -ne 0) { throw 'Unaccounted active Chroma connections' }
if ($chromaLabels.'com.docker.compose.project.working_dir' -ne 'E:\AAA_NEED\Echomind_new\EchoMind') { throw 'Unexpected Compose workspace' }
if ($context -ne 'npipe:////./pipe/dockerDesktopLinuxEngine') { throw 'Not the local Docker Desktop engine' }
if ($wslState -notmatch 'Ubuntu\s+Stopped') { throw 'Ubuntu writer surface is not stopped' }
if (@($running | Where-Object { $_ -notin 'echomind-redis','echomind-chromadb' }).Count -ne 0) { throw 'Other running containers require review' }
$record = [ordered]@{captured_at_utc=(Get-Date).ToUniversalTime().ToString('o');
    local_demo_confirmed=$true; api_stopped=$true; no_observed_writer=$true;
    explicit_stop_command='docker stop echomind-app (already exited, kept stopped)';
    processes=$processes; listeners=$listeners; established_chroma_connections=$connections;
    docker_endpoint=$context; running_containers=$running; app_state=$appState;
    chroma_labels=$chromaLabels; chroma_port_bindings=$bindings; chroma_mounts=$mounts;
    chroma_state=$chromaState; chroma_processes=$serverProcesses; wsl_state=$wslState;
    guarantee_limit='Maintenance inventory and snapshot checks; not a distributed lock against future external writers.'}
$record | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'maintenance_process.json') -Encoding utf8
Write-Output 'local_demo_confirmed=true api_stopped=true no_observed_writer=true'
