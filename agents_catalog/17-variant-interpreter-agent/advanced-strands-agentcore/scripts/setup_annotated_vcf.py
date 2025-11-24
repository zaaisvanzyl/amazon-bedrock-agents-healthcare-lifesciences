#!/usr/bin/env python3
"""
Setup script to create Glue table for VEP-annotated VCF and grant permissions
"""
import boto3
import os
import sys

# Configuration
REGION = 'us-east-1'
ACCOUNT_ID = '149536495426'
DATABASE_NAME = 'genomics_agent_db2'
ANNOTATED_TABLE_NAME = 'vcf_data_annotated'
S3_VEP_OUTPUT = 's3://genomics-vep-output-bucket-149536495426-us-east-1/vep-outputs/7199948/pubdir/annotation/clinvar_20251116/'
IAM_USER_ARN = f'arn:aws:iam::{ACCOUNT_ID}:user/zaais'

# Initialize clients
glue = boto3.client('glue', region_name=REGION)
lakeformation = boto3.client('lakeformation', region_name=REGION)
s3 = boto3.client('s3', region_name=REGION)

def drop_table_if_exists():
    """Drop the table if it already exists"""
    try:
        glue.get_table(DatabaseName=DATABASE_NAME, Name=ANNOTATED_TABLE_NAME)
        print(f"📦 Dropping existing table: {ANNOTATED_TABLE_NAME}")
        glue.delete_table(DatabaseName=DATABASE_NAME, Name=ANNOTATED_TABLE_NAME)
        print(f"✅ Dropped table: {ANNOTATED_TABLE_NAME}")
    except glue.exceptions.EntityNotFoundException:
        print(f"ℹ️  Table {ANNOTATED_TABLE_NAME} does not exist yet")

def create_annotated_vcf_table():
    """Create Glue table for VEP-annotated VCF"""
    print(f"\n📊 Creating Glue table for annotated VCF...")
    
    # VEP adds CSQ field to INFO column, but basic structure remains the same
    table_input = {
        'Name': ANNOTATED_TABLE_NAME,
        'StorageDescriptor': {
            'Columns': [
                {'Name': 'chrom', 'Type': 'string', 'Comment': 'Chromosome'},
                {'Name': 'pos', 'Type': 'bigint', 'Comment': 'Position'},
                {'Name': 'id', 'Type': 'string', 'Comment': 'Variant ID'},
                {'Name': 'ref', 'Type': 'string', 'Comment': 'Reference allele'},
                {'Name': 'alt', 'Type': 'string', 'Comment': 'Alternate allele'},
                {'Name': 'qual', 'Type': 'double', 'Comment': 'Quality score'},
                {'Name': 'filter', 'Type': 'string', 'Comment': 'Filter status'},
                {'Name': 'info', 'Type': 'string', 'Comment': 'INFO field with VEP annotations (CSQ)'},
                {'Name': 'format', 'Type': 'string', 'Comment': 'Format field'},
                {'Name': 'sample_data', 'Type': 'string', 'Comment': 'Sample genotype data'}
            ],
            'Location': S3_VEP_OUTPUT,
            'InputFormat': 'org.apache.hadoop.mapred.TextInputFormat',
            'OutputFormat': 'org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat',
            'Compressed': True,
            'SerdeInfo': {
                'SerializationLibrary': 'org.apache.hadoop.hive.serde2.lazy.LazySimpleSerDe',
                'Parameters': {
                    'field.delim': '\t',
                    'serialization.format': '\t'
                }
            },
            'StoredAsSubDirectories': False
        },
        'PartitionKeys': [],
        'TableType': 'EXTERNAL_TABLE',
        'Parameters': {
            'EXTERNAL': 'TRUE',
            'skip.header.line.count': '2',
            'comment': 'VEP-annotated VCF data',
            'compressionType': 'gzip',
            'vep_annotated': 'true'
        }
    }
    
    try:
        glue.create_table(
            DatabaseName=DATABASE_NAME,
            TableInput=table_input
        )
        print(f"✅ Created table: {DATABASE_NAME}.{ANNOTATED_TABLE_NAME}")
        return True
    except Exception as e:
        print(f"❌ Error creating table: {e}")
        return False

def grant_lake_formation_permissions():
    """Grant Lake Formation permissions for the annotated table"""
    print(f"\n🔐 Granting Lake Formation permissions...")
    
    permissions = ['SELECT', 'DESCRIBE']
    
    try:
        # Grant table permissions
        lakeformation.grant_permissions(
            Principal={'DataLakePrincipalIdentifier': IAM_USER_ARN},
            Resource={
                'Table': {
                    'DatabaseName': DATABASE_NAME,
                    'Name': ANNOTATED_TABLE_NAME
                }
            },
            Permissions=permissions
        )
        print(f"✅ Granted {permissions} permissions on {DATABASE_NAME}.{ANNOTATED_TABLE_NAME}")
        return True
    except Exception as e:
        print(f"⚠️  Warning granting table permissions: {e}")
        return False

def verify_table():
    """Verify the table was created and can be queried"""
    print(f"\n🔍 Verifying table...")
    
    try:
        table = glue.get_table(DatabaseName=DATABASE_NAME, Name=ANNOTATED_TABLE_NAME)
        print(f"✅ Table exists: {DATABASE_NAME}.{ANNOTATED_TABLE_NAME}")
        print(f"   Location: {table['Table']['StorageDescriptor']['Location']}")
        print(f"   Columns: {len(table['Table']['StorageDescriptor']['Columns'])}")
        return True
    except Exception as e:
        print(f"❌ Error verifying table: {e}")
        return False

def test_athena_query():
    """Test querying the annotated table with Athena"""
    print(f"\n🧪 Testing Athena query...")
    
    athena = boto3.client('athena', region_name=REGION)
    
    query = f"""
    SELECT chrom, pos, ref, alt, info
    FROM {DATABASE_NAME}.{ANNOTATED_TABLE_NAME}
    WHERE chrom NOT LIKE '#%'
    LIMIT 5
    """
    
    try:
        response = athena.start_query_execution(
            QueryString=query,
            QueryExecutionContext={'Database': DATABASE_NAME},
            ResultConfiguration={
                'OutputLocation': 's3://genomics-athena-results-149536495426-us-east-1/'
            }
        )
        
        query_execution_id = response['QueryExecutionId']
        print(f"✅ Started test query: {query_execution_id}")
        print(f"   You can check results with:")
        print(f"   aws athena get-query-results --query-execution-id {query_execution_id}")
        return True
    except Exception as e:
        print(f"⚠️  Could not test query: {e}")
        return False

def create_env_file():
    """Create environment file with annotated table configuration"""
    print(f"\n📝 Creating environment configuration...")
    
    env_content = f"""# VEP-Annotated VCF Configuration
AWS_DEFAULT_REGION={REGION}
AWS_REGION={REGION}
REGION={REGION}
ACCOUNT_ID={ACCOUNT_ID}
LAKE_FORMATION_DATABASE={DATABASE_NAME}

# Original VCF table (raw data)
VCF_TABLE_NAME=vcf_data

# VEP-annotated VCF table (use this for annotated queries)
VCF_ANNOTATED_TABLE_NAME={ANNOTATED_TABLE_NAME}

# Model and agent configuration
MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0
AGENT_NAME=genomics_vcf_agent

# VEP output location
VEP_OUTPUT_S3={S3_VEP_OUTPUT}
"""
    
    env_file_path = '/Users/zaaisvanzyl/Documents/GitHub/amazon-bedrock-agents-healthcare-lifesciences/agents_catalog/17-variant-interpreter-agent/advanced-strands-agentcore/.env.annotated'
    
    try:
        with open(env_file_path, 'w') as f:
            f.write(env_content)
        print(f"✅ Created: {env_file_path}")
        return True
    except Exception as e:
        print(f"❌ Error creating env file: {e}")
        return False

def main():
    print("=" * 70)
    print("🧬 Setting Up VEP-Annotated VCF for Genomics Agent")
    print("=" * 70)
    
    steps = [
        ("Dropping existing table (if any)", drop_table_if_exists),
        ("Creating annotated VCF table", create_annotated_vcf_table),
        ("Granting Lake Formation permissions", grant_lake_formation_permissions),
        ("Verifying table", verify_table),
        ("Testing Athena query", test_athena_query),
        ("Creating environment configuration", create_env_file)
    ]
    
    results = []
    for step_name, step_func in steps:
        try:
            result = step_func()
            results.append((step_name, result))
        except Exception as e:
            print(f"❌ Error in {step_name}: {e}")
            results.append((step_name, False))
    
    print("\n" + "=" * 70)
    print("📊 Setup Summary")
    print("=" * 70)
    
    for step_name, result in results:
        status = "✅" if result else "❌"
        print(f"{status} {step_name}")
    
    success_count = sum(1 for _, r in results if r)
    total_count = len(results)
    
    print("\n" + "=" * 70)
    if success_count == total_count:
        print("🎉 SUCCESS! All steps completed!")
        print("\n📋 Next Steps:")
        print("1. Update your agent to use VCF_ANNOTATED_TABLE_NAME")
        print("2. Query VEP annotations using the 'info' column (contains CSQ field)")
        print("3. Test with: python3 scripts/test_annotated_queries.py")
    else:
        print(f"⚠️  Completed {success_count}/{total_count} steps")
        print("Please check errors above and retry")
    print("=" * 70)

if __name__ == '__main__':
    main()

