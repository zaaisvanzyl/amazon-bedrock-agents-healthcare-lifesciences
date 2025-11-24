#!/bin/bash
# Deploy the fixed VCF agent

set -e

echo "=========================================="
echo "🚀 Deploying VCF Genomics Agent"
echo "=========================================="
echo ""

# Load environment
export $(cat .env.vcf | grep -v '^#' | xargs)

echo "✅ Environment loaded:"
echo "   VCF_TABLE_NAME=$VCF_TABLE_NAME"
echo "   LAKE_FORMATION_DATABASE=$LAKE_FORMATION_DATABASE"
echo ""

# Verify the agent can import tools
echo "🔍 Verifying agent tools..."
python3 << 'PYEOF'
import sys
import os
sys.path.insert(0, '.')

# Ensure environment is set
os.environ['VCF_TABLE_NAME'] = 'vcf_data'
os.environ['LAKE_FORMATION_DATABASE'] = 'genomics_agent_db2'

try:
    from agent.tools.vcf_agent_tools import vcf_agent_tools
    print(f"✅ VCF tools loaded: {len(vcf_agent_tools)} tools")
    for tool in vcf_agent_tools:
        print(f"   - {tool.__name__}")
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
PYEOF

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Agent is ready!"
    echo ""
    echo "To test locally, run:"
    echo "  cd agent"
    echo "  export \$(cat ../.env.vcf | grep -v '^#' | xargs)"
    echo "  python3 main.py"
    echo ""
    echo "To start Streamlit UI:"
    echo "  ./run_streamlit.sh"
    echo ""
else
    echo "❌ Agent deployment failed"
    exit 1
fi
