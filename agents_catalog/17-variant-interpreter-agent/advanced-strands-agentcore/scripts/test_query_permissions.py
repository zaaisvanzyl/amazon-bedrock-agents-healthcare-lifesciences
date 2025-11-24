#!/usr/bin/env python3
"""
Test Lake Formation permissions by running a simple query
"""

import boto3
import time
import sys

# Configuration
REGION = 'us-east-1'
DATABASE = 'genomics_agent_db2'
TABLE = 'variants'
ACCOUNT_ID = '149536495426'

def test_query():
    """Test a simple COUNT query to verify permissions"""
    
    print("=" * 80)
    print("🧪 Testing Lake Formation Permissions")
    print("=" * 80)
    print(f"📊 Database: {DATABASE}")
    print(f"📋 Table: {TABLE}")
    print(f"📍 Region: {REGION}")
    print("")
    
    # Initialize Athena client
    athena_client = boto3.client('athena', region_name=REGION)
    
    # Test query - count distinct samples
    query = f"""
    SELECT COUNT(DISTINCT sampleid) as patient_count
    FROM {TABLE}
    """
    
    print("📝 Query:")
    print(f"   {query.strip()}")
    print("")
    
    try:
        # Start query execution
        print("⏳ Executing query...")
        response = athena_client.start_query_execution(
            QueryString=query,
            QueryExecutionContext={'Database': DATABASE},
            WorkGroup='primary',
            ResultConfiguration={
                'OutputLocation': f's3://aws-athena-query-results-{ACCOUNT_ID}-{REGION}/'
            }
        )
        
        query_id = response['QueryExecutionId']
        print(f"✅ Query submitted: {query_id}")
        
        # Wait for query completion
        max_attempts = 30
        for attempt in range(max_attempts):
            result = athena_client.get_query_execution(QueryExecutionId=query_id)
            status = result['QueryExecution']['Status']['State']
            
            if status == 'SUCCEEDED':
                print(f"✅ Query completed successfully!")
                break
            elif status in ['FAILED', 'CANCELLED']:
                error_reason = result['QueryExecution']['Status'].get('StateChangeReason', 'Unknown error')
                print(f"❌ Query failed: {error_reason}")
                
                # Print more detailed error information
                if 'AthenaError' in result['QueryExecution']['Status']:
                    print(f"   Error details: {result['QueryExecution']['Status']['AthenaError']}")
                
                return False
            
            print(f"   Status: {status} (attempt {attempt + 1}/{max_attempts})")
            time.sleep(2)
        
        if status != 'SUCCEEDED':
            print("❌ Query timed out")
            return False
        
        # Get query results
        print("")
        print("📊 Query Results:")
        print("-" * 40)
        
        results = athena_client.get_query_results(QueryExecutionId=query_id)
        
        # Extract column names
        columns = [col['Name'] for col in results['ResultSet']['ResultSetMetadata']['ColumnInfo']]
        
        # Extract rows (skip header)
        rows = results['ResultSet']['Rows'][1:]  # Skip header row
        
        if len(rows) == 0:
            print("⚠️  No results returned")
            return False
        
        # Display results
        for row in rows:
            row_data = [col.get('VarCharValue', 'NULL') for col in row['Data']]
            for col_name, value in zip(columns, row_data):
                print(f"   {col_name}: {value}")
        
        print("")
        print("=" * 80)
        print("✅ SUCCESS! Lake Formation permissions are working correctly!")
        print("=" * 80)
        print("")
        print("The agent should now be able to query the genomics database.")
        
        # Try to parse the count
        patient_count = int(row_data[0])
        print(f"\n🧬 Found {patient_count} patient(s) in the cohort!")
        
        return True
        
    except Exception as e:
        print(f"❌ Error executing query: {e}")
        print("")
        print("Possible issues:")
        print("   1. Lake Formation permissions not granted")
        print("   2. Table doesn't exist or is empty")
        print("   3. IAM permissions insufficient")
        print("   4. S3 bucket permissions for Athena results")
        print("")
        return False


if __name__ == '__main__':
    success = test_query()
    sys.exit(0 if success else 1)

