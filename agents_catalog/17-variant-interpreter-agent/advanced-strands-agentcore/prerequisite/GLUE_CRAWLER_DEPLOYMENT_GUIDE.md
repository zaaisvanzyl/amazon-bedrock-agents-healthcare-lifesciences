# Genomics VEP Pipeline - Glue Crawler Deployment Guide

**🎯 Alternative Architecture:** This guide uses AWS Glue Crawler + Athena instead of HealthOmics Variant/Annotation Stores, which are no longer available to new customers as of November 2025.

## Architecture Overview

```
VCF Files (S3) 
    ↓
Lambda Trigger
    ↓
HealthOmics VEP Workflow
    ↓
VEP Annotated Outputs (S3)
    ↓
Glue Crawler (Auto-catalog) ← NEW!
    ↓
Glue Tables
    ↓
Athena Queries ← Agent Queries
```

## What Changed from Original Architecture

### ❌ Removed Components:
- HealthOmics Variant Stores (blocked for new customers)
- HealthOmics Annotation Stores (blocked for new customers)
- Variant Import Jobs
- EventBridge rules for import job monitoring

### ✅ New Components:
- **AWS Glue Crawler** - Automatically catalogs VEP outputs from S3
- **Updated Lambda** - Triggers Glue Crawler instead of import jobs
- **Glue Tables** - Queryable tables pointing to S3 data

### ✅ Unchanged (90% of system):
- HealthOmics VEP Workflows
- S3 Buckets
- DynamoDB Tracking
- Lake Formation Database
- All Athena SQL Queries
- Agent Tools and Logic
- Streamlit UI

## Prerequisites

Same as original system, except:
- ✅ NO need for HealthOmics Analytics permissions
- ✅ Need AWS Glue permissions (already included in CloudFormation)

## Deployment Steps

### Step 1: Deploy Updated Infrastructure

The updated `infrastructure.yaml` now includes:
- Glue Crawler resource
- Glue Crawler IAM role
- Updated Lambda environment variables
- Removed variant store dependencies

```bash
cd prerequisite/

# Deploy CloudFormation stack
aws cloudformation create-stack \
  --stack-name genomics-vep-pipeline \
  --template-body file://infrastructure.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameters \
    ParameterKey=CreateNewReferenceStore,ParameterValue=false \
    ParameterKey=ExistingReferenceStoreId,ParameterValue=YOUR_REF_STORE_ID
```

**Note:** Use your existing reference store ID from the previous deployment.

### Step 2: Upload VEP Cache and Reference Data

```bash
# Upload VEP cache (if not already done)
aws s3 sync homo_sapiens_vep_111_GRCh38/ \
  s3://genomics-vep-output-bucket-YOUR_ACCOUNT-us-east-1/vep_cache/

# Upload reference genome (if not already done)
aws s3 cp hg38_alt_aware_nohla.fa \
  s3://genomics-vep-output-bucket-YOUR_ACCOUNT-us-east-1/references/
```

### Step 3: Create HealthOmics VEP Workflow

```python
import boto3

omics = boto3.client('omics')

# Create VEP workflow (same as before)
response = omics.create_workflow(
    name='vep-workflow2',
    description='VEP annotation workflow',
    engine='NEXTFLOW',
    definitionUri='s3://YOUR_BUCKET/workflow.zip',
    parameterTemplate={
        'input_vcf': {'description': 'Input VCF file'},
        'vep_cache': {'description': 'VEP cache location'},
        'reference': {'description': 'Reference genome'}
    }
)

workflow_id = response['id']
print(f"Workflow created: {workflow_id}")
```

### Step 4: Deploy Updated Lambda Function

```bash
# Package the new Lambda function
cd lambda/
zip -r workflow-monitor-glue.zip workflow_monitor_glue_crawler.py

# Update Lambda function
aws lambda update-function-code \
  --function-name genomics-vep-pipeline-workflow-monitor \
  --zip-file fileb://workflow-monitor-glue.zip

# Update environment variables
aws lambda update-function-configuration \
  --function-name genomics-vep-pipeline-workflow-monitor \
  --environment Variables="{
    DYNAMODB_TABLE=genomics-vep-pipeline-tracking,
    DATABASE_NAME=genomics_agent_db2,
    CRAWLER_NAME=genomics-vep-pipeline-vep-crawler,
    VEP_OUTPUT_BUCKET=genomics-vep-output-bucket-YOUR_ACCOUNT-us-east-1
  }"
```

### Step 5: Configure S3 Event Notification (Optional)

To trigger the Glue Crawler immediately when VEP outputs are created:

```json
{
  "LambdaFunctionConfigurations": [
    {
      "LambdaFunctionArn": "arn:aws:lambda:REGION:ACCOUNT:function:genomics-vep-pipeline-workflow-monitor",
      "Events": ["s3:ObjectCreated:*"],
      "Filter": {
        "Key": {
          "FilterRules": [
            {
              "Name": "prefix",
              "Value": "vep-outputs/"
            },
            {
              "Name": "suffix",
              "Value": ".vcf.gz"
            }
          ]
        }
      }
    }
  ]
}
```

### Step 6: Test the Glue Crawler

```bash
# Manually trigger the crawler to test
aws glue start-crawler --name genomics-vep-pipeline-vep-crawler

# Check crawler status
aws glue get-crawler --name genomics-vep-pipeline-vep-crawler

# List tables created by crawler
aws glue get-tables --database-name genomics_agent_db2
```

### Step 7: Verify Athena Query Access

```sql
-- Test query on crawled data
SELECT * FROM genomics_agent_db2.vep_outputs LIMIT 10;

-- Check available columns
DESCRIBE genomics_agent_db2.vep_outputs;
```

## Testing End-to-End

### 1. Upload Test VCF

```bash
aws s3 cp test.vcf.gz s3://genomics-vcf-input-bucket-YOUR_ACCOUNT-us-east-1/
```

### 2. Monitor Processing

```bash
# Watch Lambda logs
aws logs tail /aws/lambda/genomics-vep-pipeline-vcf-processor --follow

# Check DynamoDB for tracking
aws dynamodb scan --table-name genomics-vep-pipeline-tracking

# Check HealthOmics run status
aws omics get-run --id RUN_ID
```

### 3. Wait for Crawler

The Glue Crawler will automatically:
1. Detect new VEP outputs in S3
2. Infer the schema
3. Create/update Glue tables
4. Make data queryable via Athena

### 4. Query with Athena

```sql
-- Find high-impact variants
SELECT 
  contigname, 
  start, 
  referenceallele, 
  alternatealleles,
  annotations
FROM genomics_agent_db2.vep_outputs
WHERE annotations LIKE '%HIGH%'
LIMIT 10;
```

## Agent Configuration

The agent code is already updated to work with Glue tables. No changes needed!

### Update Environment Variables (if needed)

```bash
# In your agent configuration
export LAKE_FORMATION_DATABASE=genomics_agent_db2
export VARIANT_STORE_NAME=vep_outputs  # Glue table name
export ANNOTATION_STORE_NAME=vep_annotations  # Glue table name (if created)
export AWS_REGION=us-east-1
```

## Troubleshooting

### Crawler Not Creating Tables

**Problem:** Crawler runs but no tables appear

**Solutions:**
1. Check crawler logs in CloudWatch
2. Verify S3 path has VEP output files
3. Ensure files are in supported format (VCF)
4. Check IAM permissions for Glue Crawler role

```bash
# Check crawler metrics
aws glue get-crawler-metrics --crawler-name-list genomics-vep-pipeline-vep-crawler

# View recent crawler runs
aws glue get-crawler --name genomics-vep-pipeline-vep-crawler \
  | jq '.Crawler.LastCrawl'
```

### Tables Created but Empty

**Problem:** Tables exist but no data returned

**Solutions:**
1. Check if VEP outputs are in correct S3 location
2. Verify file format is correct
3. Run crawler again

```bash
# Check S3 for files
aws s3 ls s3://genomics-vep-output-bucket-YOUR_ACCOUNT-us-east-1/vep-outputs/ --recursive

# Re-run crawler
aws glue start-crawler --name genomics-vep-pipeline-vep-crawler
```

### Athena Queries Failing

**Problem:** Athena queries fail with permission errors

**Solutions:**
1. Check Lake Formation permissions
2. Grant agent role access to database/tables

```bash
# Grant permissions via Lake Formation
aws lakeformation grant-permissions \
  --principal DataLakePrincipalIdentifier=arn:aws:iam::ACCOUNT:role/genomics-vep-pipeline-agent-role \
  --resource '{"Database":{"Name":"genomics_agent_db2"}}' \
  --permissions '["DESCRIBE"]'

aws lakeformation grant-permissions \
  --principal DataLakePrincipalIdentifier=arn:aws:iam::ACCOUNT:role/genomics-vep-pipeline-agent-role \
  --resource '{"Table":{"DatabaseName":"genomics_agent_db2","Name":"vep_outputs"}}' \
  --permissions '["SELECT","DESCRIBE"]'
```

## Performance Optimization

### Crawler Schedule

Run crawler on a schedule instead of per-file:

```bash
# Update crawler to run every hour
aws glue update-crawler \
  --name genomics-vep-pipeline-vep-crawler \
  --schedule "cron(0 * * * ? *)"
```

### Partitioning

For large datasets, partition by date or chromosome:

```
s3://bucket/vep-outputs/year=2025/month=11/day=23/
```

The Glue Crawler will automatically detect partitions.

## Cost Comparison

### Original (Variant Stores):
- HealthOmics Variant Store: $0.50/GB/month storage
- Import Jobs: $0.10 per job
- **Total:** ~$100-500/month depending on data volume

### New (Glue Crawler):
- S3 Storage: $0.023/GB/month
- Glue Crawler: $0.44/hour (only while running)
- Athena Queries: $5 per TB scanned
- **Total:** ~$20-100/month (50-80% savings!)

## Migration from Existing Variant Stores

If you already have data in variant stores:

### Option 1: Export and Re-catalog
```bash
# Export data from variant store (if accessible)
aws omics start-variant-export-job \
  --destination s3://bucket/exports/ \
  --source-name YOUR_VARIANT_STORE

# Run crawler on exported data
aws glue start-crawler --name genomics-vep-pipeline-vep-crawler
```

### Option 2: Dual-Path (Transition Period)
Keep both systems running during migration:
- Old queries use variant stores
- New data uses Glue tables
- Gradually migrate to 100% Glue-based

## Support

For issues specific to this deployment:
- Check CloudWatch Logs for Lambda and Glue Crawler
- Review Athena query history
- Verify Lake Formation permissions

For general HealthOmics issues:
- [AWS HealthOmics Documentation](https://docs.aws.amazon.com/omics/)
- [AWS Glue Documentation](https://docs.aws.amazon.com/glue/)

## Next Steps

1. ✅ Deploy infrastructure with Glue Crawler
2. ✅ Test with sample VCF file
3. ✅ Verify agent can query Glue tables
4. ✅ Configure Streamlit UI
5. ✅ Set up monitoring and alerts

Your genomics pipeline is now ready without variant store dependencies! 🎉

