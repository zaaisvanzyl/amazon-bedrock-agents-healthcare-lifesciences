#!/bin/bash
# Redeploy the fixed agent to Bedrock AgentCore

set -e

echo "=========================================="
echo "🚀 Redeploying Fixed VCF Agent"
echo "=========================================="
echo ""

# Load environment
export $(cat .env.vcf | grep -v '^#' | xargs)

echo "📋 Configuration:"
echo "   VCF_TABLE_NAME=$VCF_TABLE_NAME"
echo "   LAKE_FORMATION_DATABASE=$LAKE_FORMATION_DATABASE"
echo "   AWS_REGION=$AWS_DEFAULT_REGION"
echo ""

# Verify tools are working
echo "🔍 Verifying agent tools..."
python3 << 'EOF'
import sys
import os
sys.path.insert(0, '.')
os.environ['VCF_TABLE_NAME'] = 'vcf_data'
os.environ['LAKE_FORMATION_DATABASE'] = 'genomics_agent_db2'

try:
    from agent.tools.vcf_agent_tools import vcf_agent_tools
    print(f"✅ {len(vcf_agent_tools)} tools verified")
except Exception as e:
    print(f"❌ Error: {e}")
    exit(1)
EOF

if [ $? -ne 0 ]; then
    echo "❌ Agent tools verification failed"
    exit 1
fi

echo ""
echo "📦 Deploying to Bedrock AgentCore..."
echo ""

# Check if agentcore CLI is available
if command -v agentcore &> /dev/null; then
    echo "✅ AgentCore CLI found"
    
    # Get IAM role
    IAM_ROLE=$(aws iam get-role --role-name genomics-vep-pipeline-agent-role --query 'Role.Arn' --output text 2>/dev/null || echo "")
    
    if [ -z "$IAM_ROLE" ]; then
        echo "❌ Error: Could not find IAM role 'genomics-vep-pipeline-agent-role'"
        echo ""
        echo "Create it with:"
        echo "  python3 scripts/create_agent_role.py"
        exit 1
    fi
    
    echo "✅ IAM Role: $IAM_ROLE"
    echo ""
    
    # Configure AgentCore
    echo "⚙️  Configuring AgentCore..."
    agentcore configure \
        --entrypoint agent/main.py \
        --execution-role $IAM_ROLE \
        --name genomicsappvariant \
        --requirements-file agent/runtime_requirements.txt \
        --region $AWS_DEFAULT_REGION
    
    echo ""
    echo "🚀 Launching agent..."
    agentcore launch --auto-update-on-conflict
    
    echo ""
    echo "✅ Agent deployed successfully!"
    echo ""
    echo "The Streamlit UI will now use the updated agent."
    
else
    echo "❌ AgentCore CLI not found"
    echo ""
    echo "Install it with:"
    echo "  pip install bedrock-agentcore-starter-toolkit"
    echo ""
    echo "Or use Python deployment:"
    echo "  python3 scripts/deploy_to_agentcore.py"
fi

echo ""
echo "=========================================="
echo "🎉 Deployment Complete"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Wait 1-2 minutes for the runtime to update"
echo "  2. Run: ./run_streamlit.sh"
echo "  3. Ask: 'How many patients are in the present cohort?'"
echo ""

