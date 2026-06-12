#!/bin/bash

BASE="http://localhost:3000/api"

echo "=== Testing Mode Lens APIs ==="
echo ""

echo "1. Brands GET:"
curl -s $BASE/brands
echo -e "\n"

echo "2. Assets GET:"
curl -s $BASE/assets
echo -e "\n"

echo "3. Campaigns GET:"
curl -s $BASE/campaigns
echo -e "\n"

echo "4. Characters GET:"
curl -s $BASE/characters
echo -e "\n"

echo "5. Collections GET:"
curl -s $BASE/collections
echo -e "\n"

echo "6. Workflows GET:"
curl -s $BASE/workflows
echo -e "\n"

echo "7. Prompts GET:"
curl -s $BASE/prompts
echo -e "\n"

echo "8. Tags GET:"
curl -s $BASE/tags
echo -e "\n"

echo "9. Search GET (q=test):"
curl -s "$BASE/search?q=test"
echo -e "\n"

echo "10. Hybrid Search POST:"
curl -s -X POST $BASE/search/hybrid -H "Content-Type: application/json" -d '{"query":"test"}'
echo -e "\n"

echo "11. Semantic Search POST:"
curl -s -X POST $BASE/search/semantic -H "Content-Type: application/json" -d '{"query":"test"}'
echo -e "\n"

echo "12. Qdrant Status GET:"
curl -s $BASE/qdrant
echo -e "\n"

echo "13. Sync Status GET:"
curl -s $BASE/sync
echo -e "\n"

echo "14. Metadata Schema GET:"
curl -s $BASE/metadata/schema
echo -e "\n"

echo "15. Benchmark POST:"
curl -s -X POST $BASE/benchmark -H "Content-Type: application/json" -d '{"query":"test"}'
echo -e "\n"

echo "16. Brand Memory GET (no brand_id - should error):"
curl -s "$BASE/brand-memory"
echo -e "\n"

echo "17. Campaign Memory GET (no campaign_id - should error):"
curl -s "$BASE/campaign-memory"
echo -e "\n"

echo "=== Test Complete ==="
