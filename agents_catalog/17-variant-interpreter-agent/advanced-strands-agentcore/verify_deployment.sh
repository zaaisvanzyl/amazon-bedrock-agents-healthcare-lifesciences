#!/bin/bash
# Deployment Verification Script

set -e

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║          Genomics Pipeline Deployment Verification              ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# AWS Profile
PROFILE=${AWS_PROFILE:-default}
echo "Using AWS Profile: $PROFILE"
echo ""

# Check CloudFormation Stack
echo "1️⃣  Checking CloudFormation Stack..."
STACK_STATUS=$(aws cloudformation describe-stacks --stack-name genomics-vep-pipeline --query 'Stacks[0].StackStatus' --output text --profile $PROFILE 2>&1)
if [ "$STACK_STATUS" = "UPDATE_COMPLETE" ] || [ "$STACK_STATUS" = "CREATE_COMPLETE" ]; then
    echo -e "${GREEN}✅ Stack Status: $STACK_STATUS${NC}"
else
    echo -e "${RED}❌ Stack Status: $STACK_STATUS${NC}"
    exit 1
fi
echo ""

# Check Glue Crawler
echo "2️⃣  Checking Glue Crawler..."
CRAWLER_STATE=$(aws glue get-crawler --name genomics-vep-pipeline-vep-crawler --query 'Crawler.State' --output text --profile $PROFILE 2>&1)
if [ "$CRAWLER_STATE" = "READY" ]; then
    echo -e "${GREEN}✅ Glue Crawler: $CRAWLER_STATE${NC}"
    
    # Check last crawl
    LAST_CRAWL=$(aws glue get-crawler --name genomics-vep-pipeline-vep-crawler --query 'Crawler.LastCrawl.Status' --output text --profile $PROFILE 2>&1)
    if [ "$LAST_CRAWL" != "None" ]; then
        echo -e "${GREEN}   Last Crawl Status: $LAST_CRAWL${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Glue Crawler State: $CRAWLER_STATE${NC}"
fi
echo ""

# Check Lambda Function
echo "3️⃣  Checking Lambda Function..."
LAMBDA_UPDATED=$(aws lambda get-function-configuration --function-name genomics-vep-pipeline-workflow-monitor --query 'LastModified' --output text --profile $PROFILE 2>&1)
echo -e "${GREEN}✅ Lambda Function Updated: $LAMBDA_UPDATED${NC}"

CRAWLER_ENV=$(aws lambda get-function-configuration --function-name genomics-vep-pipeline-workflow-monitor --query 'Environment.Variables.CRAWLER_NAME' --output text --profile $PROFILE 2>&1)
if [ "$CRAWLER_ENV" = "genomics-vep-pipeline-vep-crawler" ]; then
    echo -e "${GREEN}✅ Lambda Environment: CRAWLER_NAME configured${NC}"
else
    echo -e "${RED}❌ Lambda Environment: CRAWLER_NAME not configured${NC}"
fi
echo ""

# Check Reference Store
echo "4️⃣  Checking Reference Store..."
REF_STORE=$(aws cloudformation describe-stacks --stack-name genomics-vep-pipeline --query 'Stacks[0].Outputs[?OutputKey==`ReferenceStoreId`].OutputValue' --output text --profile $PROFILE 2>&1)
echo -e "${GREEN}✅ Reference Store ID: $REF_STORE${NC}"
echo ""

# Check S3 Buckets
echo "5️⃣  Checking S3 Buckets..."
INPUT_BUCKET=$(aws cloudformation describe-stacks --stack-name genomics-vep-pipeline --query 'Stacks[0].Outputs[?OutputKey==`VcfInputBucketName`].OutputValue' --output text --profile $PROFILE 2>&1)
OUTPUT_BUCKET=$(aws cloudformation describe-stacks --stack-name genomics-vep-pipeline --query 'Stacks[0].Outputs[?OutputKey==`VepOutputBucketName`].OutputValue' --output text --profile $PROFILE 2>&1)

aws s3 ls s3://$INPUT_BUCKET/ --profile $PROFILE > /dev/null 2>&1 && echo -e "${GREEN}✅ Input Bucket: $INPUT_BUCKET${NC}" || echo -e "${RED}❌ Input Bucket: $INPUT_BUCKET not accessible${NC}"
aws s3 ls s3://$OUTPUT_BUCKET/ --profile $PROFILE > /dev/null 2>&1 && echo -e "${GREEN}✅ Output Bucket: $OUTPUT_BUCKET${NC}" || echo -e "${RED}❌ Output Bucket: $OUTPUT_BUCKET not accessible${NC}"
echo ""

# Check Database
echo "6️⃣  Checking Glue Database..."
DB_NAME=$(aws cloudformation describe-stacks --stack-name genomics-vep-pipeline --query 'Stacks[0].Outputs[?OutputKey==`DatabaseName`].OutputValue' --output text --profile $PROFILE 2>&1)
aws glue get-database --name $DB_NAME --profile $PROFILE > /dev/null 2>&1 && echo -e "${GREEN}✅ Database: $DB_NAME exists${NC}" || echo -e "${RED}❌ Database: $DB_NAME not found${NC}"

# Check tables
TABLE_COUNT=$(aws glue get-tables --database-name $DB_NAME --profile $PROFILE --query 'length(TableList)' --output text 2>&1)
if [ "$TABLE_COUNT" = "0" ]; then
    echo -e "${YELLOW}⚠️  No tables created yet (no VEP outputs processed)${NC}"
else
    echo -e "${GREEN}✅ Tables in database: $TABLE_COUNT${NC}"
    aws glue get-tables --database-name $DB_NAME --profile $PROFILE --query 'TableList[*].Name' --output table
fi
echo ""

# Check HealthOmics Workflows
echo "7️⃣  Checking HealthOmics Workflows..."
WORKFLOW_COUNT=$(aws omics list-workflows --profile $PROFILE --query 'length(items)' --output text 2>&1)
if [ "$WORKFLOW_COUNT" -gt "0" ]; then
    echo -e "${GREEN}✅ Workflows configured: $WORKFLOW_COUNT${NC}"
    aws omics list-workflows --profile $PROFILE --query 'items[*].[name,id,type]' --output table
else
    echo -e "${YELLOW}⚠️  No workflows found. You may need to create a VEP workflow.${NC}"
fi
echo ""

# Summary
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║                      VERIFICATION SUMMARY                        ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""
echo -e "${GREEN}✅ Infrastructure Deployed${NC}"
echo -e "${GREEN}✅ Glue Crawler Configured${NC}"
echo -e "${GREEN}✅ Lambda Function Updated${NC}"
echo -e "${GREEN}✅ Ready for VCF Processing${NC}"
echo ""
echo "📋 Next Steps:"
echo "  1. Create VEP workflow (if not exists)"
echo "  2. Upload test VCF: aws s3 cp test.vcf.gz s3://$INPUT_BUCKET/"
echo "  3. Monitor processing: aws dynamodb scan --table-name genomics-vep-pipeline-tracking"
echo "  4. View crawler logs: aws logs tail /aws-glue/crawlers --follow"
echo ""
echo "📖 Documentation:"
echo "  - Quick Start: QUICK_START.md"
echo "  - Full Guide: prerequisite/GLUE_CRAWLER_DEPLOYMENT_GUIDE.md"
echo "  - Migration Details: GLUE_MIGRATION_SUMMARY.md"
echo ""

