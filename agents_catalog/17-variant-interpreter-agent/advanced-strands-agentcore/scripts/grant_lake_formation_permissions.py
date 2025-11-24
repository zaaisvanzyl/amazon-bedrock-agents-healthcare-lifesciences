#!/usr/bin/env python3
"""
Grant Lake Formation Permissions for Genomics Agent

This script grants the necessary Lake Formation permissions to the current
IAM identity (user or role) to access the genomics database and tables.
"""

import boto3
import sys
import argparse
from botocore.exceptions import ClientError


def get_current_identity():
    """Get the current IAM identity (user or role ARN)"""
    try:
        sts = boto3.client('sts')
        identity = sts.get_caller_identity()
        
        assumed_role_arn = identity['Arn']
        account_id = identity['Account']
        
        # Convert assumed role ARN to role ARN if needed
        # From: arn:aws:sts::ACCOUNT:assumed-role/ROLENAME/SESSION
        # To: arn:aws:iam::ACCOUNT:role/ROLENAME
        if ':assumed-role/' in assumed_role_arn:
            role_name = assumed_role_arn.split('/')[-2]
            role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"
        elif ':user/' in assumed_role_arn:
            # For IAM users
            role_arn = assumed_role_arn
        else:
            role_arn = assumed_role_arn
        
        print(f"✅ Current identity: {assumed_role_arn}")
        print(f"✅ Permissions will be granted to: {role_arn}")
        
        return role_arn, account_id
        
    except Exception as e:
        print(f"❌ Error getting current identity: {e}")
        sys.exit(1)


def grant_database_permissions(lf_client, principal_arn, database_name, account_id):
    """Grant DESCRIBE permission on the database"""
    try:
        print(f"\n📋 Granting DESCRIBE permission on database '{database_name}'...")
        
        lf_client.grant_permissions(
            Principal={
                'DataLakePrincipalIdentifier': principal_arn
            },
            Resource={
                'Database': {
                    'CatalogId': account_id,
                    'Name': database_name
                }
            },
            Permissions=['DESCRIBE']
        )
        
        print(f"✅ Successfully granted DESCRIBE permission on database '{database_name}'")
        return True
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'AlreadyExistsException':
            print(f"ℹ️  Permission already exists for database '{database_name}'")
            return True
        else:
            print(f"❌ Error granting database permissions: {e}")
            return False


def grant_table_permissions(lf_client, principal_arn, database_name, table_name, account_id):
    """Grant SELECT and DESCRIBE permissions on a table"""
    try:
        print(f"\n📋 Granting SELECT and DESCRIBE permissions on table '{database_name}.{table_name}'...")
        
        lf_client.grant_permissions(
            Principal={
                'DataLakePrincipalIdentifier': principal_arn
            },
            Resource={
                'Table': {
                    'CatalogId': account_id,
                    'DatabaseName': database_name,
                    'Name': table_name
                }
            },
            Permissions=['SELECT', 'DESCRIBE']
        )
        
        print(f"✅ Successfully granted SELECT and DESCRIBE permissions on table '{database_name}.{table_name}'")
        return True
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'AlreadyExistsException':
            print(f"ℹ️  Permission already exists for table '{database_name}.{table_name}'")
            return True
        elif error_code == 'EntityNotFoundException':
            print(f"⚠️  Table '{database_name}.{table_name}' not found - skipping")
            return False
        else:
            print(f"❌ Error granting table permissions: {e}")
            return False


def grant_table_with_columns_permissions(lf_client, principal_arn, database_name, table_name, account_id):
    """Grant SELECT permission on all columns of a table"""
    try:
        print(f"\n📋 Granting SELECT permission on all columns of table '{database_name}.{table_name}'...")
        
        lf_client.grant_permissions(
            Principal={
                'DataLakePrincipalIdentifier': principal_arn
            },
            Resource={
                'TableWithColumns': {
                    'CatalogId': account_id,
                    'DatabaseName': database_name,
                    'Name': table_name,
                    'ColumnWildcard': {}
                }
            },
            Permissions=['SELECT']
        )
        
        print(f"✅ Successfully granted SELECT permission on all columns")
        return True
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'AlreadyExistsException':
            print(f"ℹ️  Permission already exists for table columns")
            return True
        elif error_code == 'EntityNotFoundException':
            print(f"⚠️  Table '{database_name}.{table_name}' not found - skipping")
            return False
        else:
            print(f"❌ Error granting column permissions: {e}")
            return False


def list_tables(glue_client, database_name):
    """List all tables in a database"""
    try:
        response = glue_client.get_tables(DatabaseName=database_name)
        tables = [table['Name'] for table in response.get('TableList', [])]
        return tables
    except ClientError as e:
        print(f"⚠️  Error listing tables: {e}")
        return []


def main():
    parser = argparse.ArgumentParser(
        description='Grant Lake Formation permissions for genomics database access'
    )
    parser.add_argument(
        '--database', 
        default='genomics_agent_db2',
        help='Name of the Lake Formation database (default: genomics_agent_db2)'
    )
    parser.add_argument(
        '--tables',
        nargs='+',
        help='Specific table names to grant permissions on (default: all tables)'
    )
    parser.add_argument(
        '--region',
        default='us-east-1',
        help='AWS region (default: us-east-1)'
    )
    parser.add_argument(
        '--principal',
        help='Principal ARN to grant permissions to (default: current identity)'
    )
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("🔐 Lake Formation Permissions Grant Script")
    print("=" * 80)
    
    # Get current identity
    if args.principal:
        principal_arn = args.principal
        sts = boto3.client('sts')
        account_id = sts.get_caller_identity()['Account']
        print(f"✅ Using specified principal: {principal_arn}")
    else:
        principal_arn, account_id = get_current_identity()
    
    # Initialize AWS clients
    lf_client = boto3.client('lakeformation', region_name=args.region)
    glue_client = boto3.client('glue', region_name=args.region)
    
    print(f"\n📊 Database: {args.database}")
    print(f"📍 Region: {args.region}")
    print(f"🆔 Account ID: {account_id}")
    
    # Grant database permissions
    db_success = grant_database_permissions(
        lf_client, 
        principal_arn, 
        args.database, 
        account_id
    )
    
    if not db_success:
        print("\n❌ Failed to grant database permissions. Please check:")
        print("   1. You have lakeformation:GrantPermissions permission")
        print("   2. The database name is correct")
        print("   3. You have administrative access to Lake Formation")
        sys.exit(1)
    
    # Get list of tables
    if args.tables:
        tables = args.tables
        print(f"\n📋 Processing specified tables: {', '.join(tables)}")
    else:
        print(f"\n📋 Discovering tables in database '{args.database}'...")
        tables = list_tables(glue_client, args.database)
        
        if not tables:
            print(f"⚠️  No tables found in database '{args.database}'")
            print("\nPossible reasons:")
            print("   1. Database is empty")
            print("   2. Glue Crawler hasn't run yet")
            print("   3. You don't have Glue permissions to list tables")
            print("\nYou can:")
            print(f"   - Run: python {sys.argv[0]} --database {args.database} --tables <table_name>")
            print("   - Or check the AWS Glue console to verify tables exist")
            sys.exit(0)
        
        print(f"✅ Found {len(tables)} tables: {', '.join(tables)}")
    
    # Grant permissions for each table
    successful_tables = []
    failed_tables = []
    
    for table_name in tables:
        # Grant table-level permissions
        table_success = grant_table_permissions(
            lf_client,
            principal_arn,
            args.database,
            table_name,
            account_id
        )
        
        # Grant column-level permissions
        column_success = grant_table_with_columns_permissions(
            lf_client,
            principal_arn,
            args.database,
            table_name,
            account_id
        )
        
        if table_success or column_success:
            successful_tables.append(table_name)
        else:
            failed_tables.append(table_name)
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)
    print(f"✅ Database permissions: Granted for '{args.database}'")
    print(f"✅ Tables processed successfully: {len(successful_tables)}")
    
    if successful_tables:
        for table in successful_tables:
            print(f"   - {table}")
    
    if failed_tables:
        print(f"\n⚠️  Tables with issues: {len(failed_tables)}")
        for table in failed_tables:
            print(f"   - {table}")
    
    print("\n✨ Lake Formation permissions have been configured!")
    print("\nYou can now:")
    print("   1. Query the database using Athena")
    print("   2. Run the genomics agent")
    print("   3. Execute SQL queries on the tables")
    
    print("\nTo verify permissions, run:")
    print(f"   aws lakeformation list-permissions --principal DataLakePrincipalIdentifier={principal_arn}")


if __name__ == '__main__':
    main()

