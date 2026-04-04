param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$SystemComponentName = "payment-api",
    [switch]$CreateSampleComponent
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Send-McpRequest {
    param(
        [string]$Id,
        [string]$Method,
        [hashtable]$Params
    )

    $body = @{
        jsonrpc = "2.0"
        id = $Id
        method = $Method
        params = $Params
    } | ConvertTo-Json -Depth 10

    Invoke-RestMethod -Method Post -Uri "$BaseUrl/mcp" -ContentType "application/json" -Body $body
}

function Print-Json {
    param($Value)
    $Value | ConvertTo-Json -Depth 20
}

Write-Step "Checking API health"
$health = Invoke-RestMethod -Method Get -Uri "$BaseUrl/health"
Print-Json $health

if ($CreateSampleComponent) {
    Write-Step "Creating sample system component '$SystemComponentName' (ignore conflict if already exists)"
    $createBody = @{
        name = $SystemComponentName
        description = "manual mcp test"
    } | ConvertTo-Json

    try {
        $created = Invoke-RestMethod -Method Post -Uri "$BaseUrl/system-components" -ContentType "application/json" -Body $createBody
        Print-Json $created
    }
    catch {
        $statusCode = $_.Exception.Response.StatusCode.value__
        if ($statusCode -eq 409) {
            Write-Host "System component already exists, continuing..." -ForegroundColor Yellow
        }
        else {
            throw
        }
    }
}

Write-Step "MCP initialize"
$initialize = Send-McpRequest -Id "init-1" -Method "initialize" -Params @{
    protocolVersion = "2025-03-26"
    clientInfo = @{
        name = "manual-mcp-test"
        version = "0.1"
    }
}
Print-Json $initialize

Write-Step "MCP tools/list"
$toolsList = Send-McpRequest -Id "tools-1" -Method "tools/list" -Params @{}
Print-Json $toolsList

Write-Step "MCP tools/call: context.system.current_state"
$currentState = Send-McpRequest -Id "call-1" -Method "tools/call" -Params @{
    name = "context.system.current_state"
    arguments = @{}
}
Print-Json $currentState

Write-Step "MCP tools/call: context.system_component.get"
$componentContext = Send-McpRequest -Id "call-2" -Method "tools/call" -Params @{
    name = "context.system_component.get"
    arguments = @{
        name = $SystemComponentName
    }
}
Print-Json $componentContext

Write-Step "Done"
Write-Host "Manual MCP test flow completed." -ForegroundColor Green
