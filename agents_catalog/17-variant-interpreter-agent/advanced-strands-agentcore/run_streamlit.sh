#!/bin/bash
# Startup script for Genomics VCF Agent Streamlit UI

set -e

echo "=========================================="
echo "🧬 Starting Genomics VCF Agent UI"
echo "=========================================="
echo ""

# Load environment variables
if [ -f ".env.vcf" ]; then
    echo "📝 Loading environment variables from .env.vcf..."
    export $(cat .env.vcf | grep -v '^#' | xargs)
    echo "✅ Environment loaded"
else
    echo "⚠️  Warning: .env.vcf not found, using defaults"
fi

# Display configuration
echo ""
echo "Configuration:"
echo "  Database: ${LAKE_FORMATION_DATABASE:-genomics_agent_db2}"
echo "  Table: ${VCF_TABLE_NAME:-vcf_data}"
echo "  Region: ${AWS_DEFAULT_REGION:-us-east-1}"
echo ""

# Check AWS credentials
echo "🔐 Checking AWS credentials..."
if aws sts get-caller-identity > /dev/null 2>&1; then
    IDENTITY=$(aws sts get-caller-identity --query 'Arn' --output text)
    echo "✅ AWS credentials valid: $IDENTITY"
else
    echo "❌ AWS credentials not configured"
    echo "Please configure AWS CLI with: aws configure"
    exit 1
fi

# Check Lake Formation permissions
echo ""
echo "🔍 Checking database access..."
TABLE_COUNT=$(aws glue get-tables --database-name ${LAKE_FORMATION_DATABASE:-genomics_agent_db2} --region ${AWS_DEFAULT_REGION:-us-east-1} 2>/dev/null | jq '.TableList | length' || echo "0")

if [ "$TABLE_COUNT" -gt 0 ]; then
    echo "✅ Database accessible: $TABLE_COUNT tables found"
else
    echo "⚠️  Warning: Cannot access database or no tables found"
    echo "Run: ./scripts/grant_lake_formation_permissions.sh"
fi

echo ""
echo "🚀 Starting Streamlit app..."
echo ""
echo "=========================================="
echo ""

# Start Streamlit
streamlit run app.py \
    --server.port 8501 \
    --server.address localhost \
    --server.headless true \
    --theme.base light

echo ""
echo "=========================================="
echo "✅ Streamlit app stopped"
echo "=========================================="

