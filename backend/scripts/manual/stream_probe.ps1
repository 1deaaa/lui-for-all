$ErrorActionPreference = 'Stop'
$base = 'http://127.0.0.1:6689'

$projects = Invoke-RestMethod -Uri "$base/api/projects/" -Method Get -TimeoutSec 10
$project = $projects.projects | Where-Object { $_.name -eq 'FastAPI 示例' } | Select-Object -First 1
if (-not $project) {
    $project = $projects.projects | Select-Object -First 1
}
if (-not $project) {
    throw '没有可用项目，无法执行聊天测试。'
}

Write-Host "Using project: $($project.id) $($project.name)"

$session = Invoke-RestMethod -Uri "$base/api/sessions/" -Method Post -ContentType 'application/json' -Body (@{ project_id = $project.id } | ConvertTo-Json) -TimeoutSec 15
$sid = $session.session_id
Write-Host "session_id=$sid"

# 第一轮：direct 路径
$directPrompt = '这是后端流式实测。请直接回复：后端正在流式输出。然后再补一句：我已完成验证。'
$directMessage = Invoke-RestMethod -Uri "$base/api/sessions/$sid/messages" -Method Post -ContentType 'application/json' -Body (@{ content = $directPrompt } | ConvertTo-Json -Depth 5) -TimeoutSec 20
$directTaskId = $directMessage.task_run_id
Write-Host "direct_task_run_id=$directTaskId"

function Invoke-SseProbe {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SessionId,
        [Parameter(Mandatory = $true)]
        [string]$TaskRunId,
        [Parameter(Mandatory = $true)]
        [string]$Label,
        [int]$TimeoutSeconds = 120
    )

    $url = "$base/api/sessions/$SessionId/events/stream?task_run_id=$TaskRunId&locale=zh-CN"
    Write-Host "[$Label] SSE=$url"

    $client = [System.Net.Http.HttpClient]::new()
    $client.Timeout = [TimeSpan]::FromSeconds($TimeoutSeconds)

    $req = [System.Net.Http.HttpRequestMessage]::new([System.Net.Http.HttpMethod]::Get, $url)
    $req.Headers.Accept.ParseAdd('text/event-stream')

    $resp = $client.SendAsync($req, [System.Net.Http.HttpCompletionOption]::ResponseHeadersRead).GetAwaiter().GetResult()
    Write-Host "[$Label] status=$([int]$resp.StatusCode)"

    $reader = New-Object System.IO.StreamReader($resp.Content.ReadAsStreamAsync().GetAwaiter().GetResult())
    $sw = [System.Diagnostics.Stopwatch]::StartNew()

    $lastEvent = ''
    $tokenEvents = 0
    $tokenChars = 0
    $toolEvents = 0
    $firstTokenMs = $null
    $lastTokenMs = $null
    $completed = $false

    while (-not $reader.EndOfStream) {
        if ($sw.Elapsed.TotalSeconds -gt $TimeoutSeconds) {
            Write-Host "[$Label] timeout"
            break
        }

        $line = $reader.ReadLine()
        if ($null -eq $line) {
            continue
        }

        if ($line.StartsWith('event:')) {
            $lastEvent = $line.Substring(6).Trim()
            $ms = [math]::Round($sw.Elapsed.TotalMilliseconds)
            if ($lastEvent -in @('task_started','task_progress','agentic_iteration','tool_started','tool_completed','token_emitted','task_completed','error')) {
                Write-Host ("[{0}] [{1,6}ms] event={2}" -f $Label, $ms, $lastEvent)
            }
            continue
        }

        if ($line.StartsWith('data:')) {
            $payload = $line.Substring(5).Trim()
            $ms = [math]::Round($sw.Elapsed.TotalMilliseconds)
            $obj = $null
            try {
                $obj = $payload | ConvertFrom-Json
            } catch {
                $obj = $null
            }

            if ($lastEvent -eq 'token_emitted') {
                $token = ''
                if ($obj -and $obj.token) {
                    $token = [string]$obj.token
                }
                $tokenEvents++
                $tokenChars += $token.Length
                if ($null -eq $firstTokenMs) {
                    $firstTokenMs = $ms
                }
                $lastTokenMs = $ms

                $preview = $token.Replace("`r", ' ').Replace("`n", '⏎')
                if ($preview.Length -gt 24) {
                    $preview = $preview.Substring(0, 24) + '...'
                }
                Write-Host ("[{0}] [{1,6}ms] token#{2} len={3} text={4}" -f $Label, $ms, $tokenEvents, $token.Length, $preview)
            } elseif ($lastEvent -eq 'tool_started') {
                $toolEvents++
                $title = if ($obj -and $obj.title) { [string]$obj.title } else { '' }
                Write-Host ("[{0}] [{1,6}ms] tool#{2} {3}" -f $Label, $ms, $toolEvents, $title)
            } elseif ($lastEvent -eq 'task_completed') {
                $summary = ''
                if ($obj -and $obj.summary) {
                    $summary = [string]$obj.summary
                }
                $summaryPreview = $summary.Replace("`r", ' ').Replace("`n", '⏎')
                if ($summaryPreview.Length -gt 90) {
                    $summaryPreview = $summaryPreview.Substring(0, 90) + '...'
                }
                Write-Host ("[{0}] [{1,6}ms] completed summary={2}" -f $Label, $ms, $summaryPreview)
                $completed = $true
                break
            } elseif ($lastEvent -eq 'error') {
                Write-Host ("[{0}] [{1,6}ms] error payload={2}" -f $Label, $ms, $payload)
                break
            }
        }
    }

    $sw.Stop()

    Write-Host "[$Label] --- SUMMARY ---"
    Write-Host "[$Label] token_events=$tokenEvents"
    Write-Host "[$Label] token_chars=$tokenChars"
    Write-Host "[$Label] tool_events=$toolEvents"
    Write-Host "[$Label] first_token_ms=$firstTokenMs"
    Write-Host "[$Label] last_token_ms=$lastTokenMs"
    if ($firstTokenMs -ne $null -and $lastTokenMs -ne $null) {
        Write-Host "[$Label] token_span_ms=$($lastTokenMs - $firstTokenMs)"
    }
    Write-Host "[$Label] task_completed=$completed"

    return [pscustomobject]@{
        Label = $Label
        TokenEvents = $tokenEvents
        TokenChars = $tokenChars
        ToolEvents = $toolEvents
        FirstTokenMs = $firstTokenMs
        LastTokenMs = $lastTokenMs
        TokenSpanMs = if ($firstTokenMs -ne $null -and $lastTokenMs -ne $null) { $lastTokenMs - $firstTokenMs } else { $null }
        Completed = $completed
    }
}

$directResult = Invoke-SseProbe -SessionId $sid -TaskRunId $directTaskId -Label 'direct' -TimeoutSeconds 90

# 第二轮：agentic 路径（同一个会话继续）
$agenticPrompt = '请调用接口读取一条真实数据，再用120字以上总结你做了什么和结果。'
$agenticMessage = Invoke-RestMethod -Uri "$base/api/sessions/$sid/messages" -Method Post -ContentType 'application/json' -Body (@{ content = $agenticPrompt } | ConvertTo-Json -Depth 5) -TimeoutSec 20
$agenticTaskId = $agenticMessage.task_run_id
Write-Host "agentic_task_run_id=$agenticTaskId"

$agenticResult = Invoke-SseProbe -SessionId $sid -TaskRunId $agenticTaskId -Label 'agentic' -TimeoutSeconds 150

Write-Host '===== FINAL CHECK ====='
$directLine = "direct: tokens=$($directResult.TokenEvents), span_ms=$($directResult.TokenSpanMs), completed=$($directResult.Completed)"
$agenticLine = "agentic: tokens=$($agenticResult.TokenEvents), span_ms=$($agenticResult.TokenSpanMs), tools=$($agenticResult.ToolEvents), completed=$($agenticResult.Completed)"
Write-Host $directLine
Write-Host $agenticLine
