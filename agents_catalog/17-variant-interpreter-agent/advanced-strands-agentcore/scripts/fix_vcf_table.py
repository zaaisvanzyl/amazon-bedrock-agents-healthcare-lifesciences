#!/usr/bin/env python3
"""
Fix the VCF table by creating a new table that can properly read VCF data
"""

import boto3
import time
import sys

REGION = 'us-east-1'
DATABASE = 'genomics_agent_db2'
ACCOUNT_ID = '149536495426'

athena_client = boto3.client('athena', region_name=REGION)

def execute_athena_ddl(query):
    """Execute a DDL query in Athena"""
    print(f"Executing query:\n{query}\n")
    
    response = athena_client.start_query_execution(
        QueryString=query,
        QueryExecutionContext={'Database': DATABASE},
        WorkGroup='primary',
        ResultConfiguration={
            'OutputLocation': f's3://aws-athena-query-results-{ACCOUNT_ID}-{REGION}/'
        }
    )
    
    query_id = response['QueryExecutionId']
    print(f"Query ID: {query_id}")
    
    # Wait for completion
    max_attempts = 30
    for attempt in range(max_attempts):
        result = athena_client.get_query_execution(QueryExecutionId=query_id)
        status = result['QueryExecution']['Status']['State']
        
        if status == 'SUCCEEDED':
            print("✅ Query succeeded!")
            return True
        elif status in ['FAILED', 'CANCELLED']:
            error_reason = result['QueryExecution']['Status'].get('StateChangeReason', 'Unknown error')
            print(f"❌ Query failed: {error_reason}")
            return False
        
        print(f"  Status: {status} (attempt {attempt + 1}/{max_attempts})")
        time.sleep(2)
    
    print("❌ Query timed out")
    return False

def main():
    print("=" * 80)
    print("🔧 Fixing VCF Table")
    print("=" * 80)
    print()
    
    # Step 1: Drop existing vcf_data table if it exists
    print("Step 1: Dropping existing vcf_data table if it exists...")
    drop_query = "DROP TABLE IF EXISTS genomics_agent_db2.vcf_data"
    execute_athena_ddl(drop_query)
    print()
    
    # Step 2: Create new table with proper VCF handling
    print("Step 2: Creating new vcf_data table...")
    create_query = """
    CREATE EXTERNAL TABLE genomics_agent_db2.vcf_data (
      chrom STRING,
      pos BIGINT,
      id STRING,
      ref STRING,
      alt STRING,
      qual DOUBLE,
      filter STRING,
      info STRING
    )
    ROW FORMAT DELIMITED
    FIELDS TERMINATED BY '\t'
    STORED AS TEXTFILE
    LOCATION 's3://genomics-vep-output-bucket-149536495426-us-east-1/vep-outputs-uncompressed/'
    TBLPROPERTIES (
      'skip.header.line.count'='2',
      'serialization.null.format'=''
    )
    """
    
    if not execute_athena_ddl(create_query):
        print("\n❌ Failed to create table")
        sys.exit(1)
    
    print()
    print("Step 3: Granting Lake Formation permissions on new table...")
    
    # Grant Lake Formation permissions
    lf_client = boto3.client('lakeformation', region_name=REGION)
    sts = boto3.client('sts')
    identity = sts.get_caller_identity()
    
    assumed_role_arn = identity['Arn']
    if ':assumed-role/' in assumed_role_arn:
        role_name = assumed_role_arn.split('/')[-2]
        principal_arn = f"arn:aws:iam::{ACCOUNT_ID}:role/{role_name}"
    else:
        principal_arn = assumed_role_arn
    
    print(f"  Principal: {principal_arn}")
    
    try:
        # Grant table permissions
        lf_client.grant_permissions(
            Principal={'DataLakePrincipalIdentifier': principal_arn},
            Resource={
                'Table': {
                    'CatalogId': ACCOUNT_ID,
                    'DatabaseName': DATABASE,
                    'Name': 'vcf_data'
                }
            },
            Permissions=['SELECT', 'DESCRIBE']
        )
        print("  ✅ Table permissions granted")
    except Exception as e:
        if 'AlreadyExistsException' in str(e):
            print("  ℹ️  Permissions already exist")
        else:
            print(f"  ⚠️  Warning: {e}")
    
    try:
        # Grant column permissions
        lf_client.grant_permissions(
            Principal={'DataLakePrincipalIdentifier': principal_arn},
            Resource={
                'TableWithColumns': {
                    'CatalogId': ACCOUNT_ID,
                    'DatabaseName': DATABASE,
                    'Name': 'vcf_data',
                    'ColumnWildcard': {}
                }
            },
            Permissions=['SELECT']
        )
        print("  ✅ Column permissions granted")
    except Exception as e:
        if 'AlreadyExistsException' in str(e):
            print("  ℹ️  Permissions already exist")
        else:
            print(f"  ⚠️  Warning: {e}")
    
    print()
    print("Step 4: Testing the new table...")
    
    # Test query
    test_query = "SELECT COUNT(*) as variant_count FROM vcf_data"
    
    response = athena_client.start_query_execution(
        QueryString=test_query,
        QueryExecutionContext={'Database': DATABASE},
        WorkGroup='primary',
        ResultConfiguration={
            'OutputLocation': f's3://aws-athena-query-results-{ACCOUNT_ID}-{REGION}/'
        }
    )
    
    query_id = response['QueryExecutionId']
    
    # Wait for completion
    for attempt in range(30):
        result = athena_client.get_query_execution(QueryExecutionId=query_id)
        status = result['QueryExecution']['Status']['State']
        
        if status == 'SUCCEEDED':
            break
        elif status in ['FAILED', 'CANCELLED']:
            error_reason = result['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
            print(f"❌ Test query failed: {error_reason}")
            sys.exit(1)
        
        time.sleep(2)
    
    # Get results
    results = athena_client.get_query_results(QueryExecutionId=query_id)
    rows = results['ResultSet']['Rows']
    
    if len(rows) > 1:
        variant_count = rows[1]['Data'][0].get('VarCharValue', '0')
        print(f"✅ Table is working! Found {variant_count} variants")
    else:
        print("⚠️  Table created but no data found")
    
    print()
    print("=" * 80)
    print("✅ SUCCESS! VCF table has been fixed")
    print("=" * 80)
    print()
    print("The table 'genomics_agent_db2.vcf_data' can now be queried.")
    print()
    print("Test it with:")
    print("  SELECT * FROM genomics_agent_db2.vcf_data LIMIT 10;")

if __name__ == '__main__':
    main()

