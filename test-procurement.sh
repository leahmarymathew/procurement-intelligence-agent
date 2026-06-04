#!/bin/bash

API_BASE="http://localhost:8000"

echo "================================="
echo "Submitting Procurement Requests"
echo "================================="
echo ""

# Array of supplier requests
suppliers=(
    '{"requester":"John Smith","supplier_name":"TechCorp Solutions","category":"IT Services","value":15000,"currency":"USD","description":"Cloud infrastructure migration and setup","pilot_team":"pilot-alpha"}'
    '{"requester":"Sarah Johnson","supplier_name":"Global Parts Manufacturing","category":"Manufacturing","value":45000,"currency":"USD","description":"Raw material procurement for Q2 production","pilot_team":"pilot-alpha"}'
    '{"requester":"Michael Chen","supplier_name":"Premium Logistics Inc","category":"Logistics","value":8500,"currency":"USD","description":"International shipping and customs clearance","pilot_team":"pilot-beta"}'
    '{"requester":"Emma Wilson","supplier_name":"Enterprise Security Group","category":"Security Services","value":22000,"currency":"USD","description":"Annual cybersecurity audit and vulnerability assessment","pilot_team":"pilot-beta"}'
    '{"requester":"David Brown","supplier_name":"DataFlow Analytics","category":"Data Services","value":35000,"currency":"USD","description":"Real-time data pipeline implementation and support","pilot_team":"pilot-alpha"}'
    '{"requester":"Lisa Garcia","supplier_name":"Office Solutions Ltd","category":"Facilities","value":5500,"currency":"USD","description":"Office equipment and furniture procurement","pilot_team":"pilot-beta"}'
    '{"requester":"Robert Taylor","supplier_name":"ConsultPro Advisors","category":"Consulting","value":28000,"currency":"USD","description":"Strategic business process optimization consultation","pilot_team":"pilot-alpha"}'
    '{"requester":"Michelle Martinez","supplier_name":"Compliance & Legal Experts","category":"Legal","value":12000,"currency":"USD","description":"Regulatory compliance review and legal documentation","pilot_team":"pilot-beta"}'
)

submitted=0

for json in "${suppliers[@]}"; do
    supplier=$(echo "$json" | grep -o '"supplier_name":"[^"]*"' | cut -d'"' -f4)
    requester=$(echo "$json" | grep -o '"requester":"[^"]*"' | cut -d'"' -f4)
    value=$(echo "$json" | grep -o '"value":[0-9]*' | cut -d':' -f2)

    echo "Submitting: $supplier"
    echo "  Requester: $requester | Value: USD $value"

    response=$(curl -s -X POST "$API_BASE/procurement/request" \
        -H "Content-Type: application/json" \
        -d "$json")

    request_id=$(echo "$response" | grep -o '"request_id":"[^"]*"' | cut -d'"' -f4)

    if [ -n "$request_id" ]; then
        echo "  ✓ Request ID: $request_id"
        submitted=$((submitted + 1))
    else
        echo "  ✗ Error submitting request"
    fi

    sleep 0.3
done

echo ""
echo "Submitted $submitted requests"
echo "Waiting for agents to process..."
sleep 6

echo ""
echo "✓ Test Complete!"
echo "Dashboard: http://localhost:5173"
echo "API Docs: http://localhost:8000/docs"
