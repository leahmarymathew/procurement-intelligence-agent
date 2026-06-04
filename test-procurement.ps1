param()

$apiBase = "http://localhost:8000"

$requests = @(
    @{requester="John Smith"; supplier_name="TechCorp Solutions"; category="IT Services"; value=15000; description="Cloud infrastructure migration"; pilot_team="pilot-alpha"},
    @{requester="Sarah Johnson"; supplier_name="Global Parts Manufacturing"; category="Manufacturing"; value=45000; description="Raw material procurement for Q2"; pilot_team="pilot-alpha"},
    @{requester="Michael Chen"; supplier_name="Premium Logistics Inc"; category="Logistics"; value=8500; description="International shipping"; pilot_team="pilot-beta"},
    @{requester="Emma Wilson"; supplier_name="Enterprise Security Group"; category="Security Services"; value=22000; description="Cybersecurity audit"; pilot_team="pilot-beta"},
    @{requester="David Brown"; supplier_name="DataFlow Analytics"; category="Data Services"; value=35000; description="Data pipeline implementation"; pilot_team="pilot-alpha"},
    @{requester="Lisa Garcia"; supplier_name="Office Solutions Ltd"; category="Facilities"; value=5500; description="Office equipment procurement"; pilot_team="pilot-beta"},
    @{requester="Robert Taylor"; supplier_name="ConsultPro Advisors"; category="Consulting"; value=28000; description="Business optimization consultation"; pilot_team="pilot-alpha"},
    @{requester="Michelle Martinez"; supplier_name="Compliance & Legal Experts"; category="Legal"; value=12000; description="Regulatory compliance review"; pilot_team="pilot-beta"}
)

Write-Host "=================================" -ForegroundColor Cyan
Write-Host "Submitting Procurement Requests" -ForegroundColor Cyan
Write-Host "=================================" -ForegroundColor Cyan
Write-Host ""

$submitted_count = 0

foreach ($req in $requests) {
    $json = $req | ConvertTo-Json
    Write-Host "Submitting: $($req.supplier_name)" -ForegroundColor Yellow
    Write-Host "  Requester: $($req.requester) | Value: USD $($req.value)" -ForegroundColor Gray

    try {
        $uri = "$apiBase/procurement/request"
        $request = [System.Net.HttpWebRequest]::Create($uri)
        $request.Method = "POST"
        $request.ContentType = "application/json"

        $body = [System.Text.Encoding]::UTF8.GetBytes($json)
        $request.ContentLength = $body.Length

        $stream = $request.GetRequestStream()
        $stream.Write($body, 0, $body.Length)
        $stream.Close()

        $response = $request.GetResponse()
        $reader = New-Object System.IO.StreamReader($response.GetResponseStream())
        $content = $reader.ReadToEnd()
        $reader.Close()

        $result = $content | ConvertFrom-Json
        Write-Host "  ✓ Request ID: $($result.request_id)" -ForegroundColor Green
        $submitted_count++
    }
    catch {
        Write-Host "  ✗ Error: $_" -ForegroundColor Red
    }

    Start-Sleep -Milliseconds 300
}

Write-Host ""
Write-Host "Submitted $submitted_count requests" -ForegroundColor Cyan
Write-Host "Waiting for agents to process..." -ForegroundColor Yellow
Start-Sleep -Seconds 6

Write-Host ""
Write-Host "✓ Test Complete!" -ForegroundColor Green
Write-Host "Dashboard: http://localhost:5173" -ForegroundColor Cyan
Write-Host "API Docs: http://localhost:8000/docs" -ForegroundColor Cyan
