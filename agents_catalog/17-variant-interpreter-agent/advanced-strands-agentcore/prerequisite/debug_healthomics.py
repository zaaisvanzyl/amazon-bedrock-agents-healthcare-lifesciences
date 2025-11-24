#!/usr/bin/env python3
"""
Debug script to diagnose HealthOmics API issues
"""

import boto3
import json
from botocore import __version__ as botocore_version

# Configuration
AWS_PROFILE = 'default'
AWS_REGION = 'us-east-1'
REFERENCE_STORE_ID = '3068761940'
REFERENCE_GENOME_ID = '3103983336'  # GRCh38_hg38

print("=" * 60)
print("HealthOmics Debug Script")
print("=" * 60)
print()

# Check versions
print("1. Checking boto3/botocore versions:")
print(f"   boto3 version: {boto3.__version__}")
print(f"   botocore version: {botocore_version}")
print()

# Create session
session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
omics_client = session.client('omics')
sts_client = session.client('sts')

# Get account info
account_id = sts_client.get_caller_identity()['Account']
print(f"2. AWS Account ID: {account_id}")
print(f"   Region: {AWS_REGION}")
print()

# Check if we can list stores (read operations)
print("3. Testing READ operations:")
try:
    variant_stores = omics_client.list_variant_stores()
    print(f"   ✅ list_variant_stores: SUCCESS ({len(variant_stores.get('variantStores', []))} stores)")
except Exception as e:
    print(f"   ❌ list_variant_stores: FAILED - {e}")

try:
    annotation_stores = omics_client.list_annotation_stores()
    print(f"   ✅ list_annotation_stores: SUCCESS ({len(annotation_stores.get('annotationStores', []))} stores)")
except Exception as e:
    print(f"   ❌ list_annotation_stores: FAILED - {e}")

try:
    reference_stores = omics_client.list_reference_stores()
    print(f"   ✅ list_reference_stores: SUCCESS ({len(reference_stores.get('referenceStores', []))} stores)")
except Exception as e:
    print(f"   ❌ list_reference_stores: FAILED - {e}")

print()

# Verify reference store exists
print("4. Verifying Reference Store:")
try:
    ref_store = omics_client.get_reference_store(id=REFERENCE_STORE_ID)
    print(f"   ✅ Reference Store {REFERENCE_STORE_ID} exists")
    print(f"      Name: {ref_store.get('name', 'N/A')}")
    print(f"      ARN: {ref_store.get('arn', 'N/A')}")
except Exception as e:
    print(f"   ❌ Reference Store {REFERENCE_STORE_ID} NOT FOUND: {e}")
    print(f"      This is the problem! The reference store doesn't exist.")
    print()
    print("   Available Reference Stores:")
    try:
        stores = omics_client.list_reference_stores()
        if stores.get('referenceStores'):
            for store in stores['referenceStores']:
                print(f"      - ID: {store['id']}, Name: {store.get('name', 'N/A')}")
        else:
            print("      No reference stores found in this account/region")
    except Exception as e2:
        print(f"      Could not list reference stores: {e2}")

print()

# Verify reference genome exists
print("5. Verifying Reference Genome:")
try:
    ref_genome = omics_client.get_reference_metadata(
        referenceStoreId=REFERENCE_STORE_ID,
        id=REFERENCE_GENOME_ID
    )
    print(f"   ✅ Reference Genome {REFERENCE_GENOME_ID} exists in store {REFERENCE_STORE_ID}")
    print(f"      Name: {ref_genome.get('name', 'N/A')}")
    print(f"      ARN: {ref_genome.get('arn', 'N/A')}")
except Exception as e:
    print(f"   ❌ Reference Genome {REFERENCE_GENOME_ID} NOT FOUND: {e}")
    print(f"      This could be the problem!")
    print()
    print(f"   Available References in store {REFERENCE_STORE_ID}:")
    try:
        refs = omics_client.list_references(referenceStoreId=REFERENCE_STORE_ID)
        if refs.get('references'):
            for ref in refs['references']:
                print(f"      - ID: {ref['id']}, Name: {ref.get('name', 'N/A')}")
        else:
            print("      No references found in this store")
    except Exception as e2:
        print(f"      Could not list references: {e2}")

print()

# Try to create a variant store with detailed error handling
print("6. Testing CREATE operations:")
print()
print("   Attempting to create variant store...")

reference_arn = f'arn:aws:omics:{AWS_REGION}:{account_id}:referenceStore/{REFERENCE_STORE_ID}/reference/{REFERENCE_GENOME_ID}'
print(f"   Reference ARN: {reference_arn}")
print()

try:
    # Check if omics client has the create_variant_store method
    if not hasattr(omics_client, 'create_variant_store'):
        print("   ❌ ERROR: omics_client doesn't have 'create_variant_store' method!")
        print("      Your boto3/botocore version is too old!")
        print(f"      Current botocore: {botocore_version}")
        print("      Required: >= 1.31.0")
        print()
        print("   To fix, run:")
        print("      pip install --upgrade boto3 botocore")
    else:
        print("   ✅ create_variant_store method exists")
        print()
        print("   Attempting to create test variant store...")
        
        test_store_name = f'test-variant-store-{account_id[-4:]}'
        
        response = omics_client.create_variant_store(
            name=test_store_name,
            description='Test variant store for debugging',
            reference={
                'referenceArn': reference_arn
            }
        )
        
        print(f"   ✅ SUCCESS! Created variant store: {response['id']}")
        print(f"      Name: {response['name']}")
        print(f"      Status: {response['status']}")
        print()
        print("   🎉 The API works! Your main script should work now.")
        print()
        print(f"   Note: Clean up test store later with:")
        print(f"      aws omics delete-variant-store --name {test_store_name}")
        
except Exception as e:
    print(f"   ❌ FAILED to create variant store")
    print(f"      Error type: {type(e).__name__}")
    print(f"      Error message: {str(e)}")
    print()
    
    # Check if it's a boto3 version issue
    if 'operation' in str(e).lower() and 'unknown' in str(e).lower():
        print("   💡 This looks like a boto3 version issue!")
        print("      Try: pip install --upgrade boto3 botocore")
    elif 'referenceArn' in str(e):
        print("   💡 This looks like an invalid reference ARN issue!")
        print("      Check that the reference store and genome IDs are correct")
    elif 'Unable to determine service/operation name' in str(e):
        print("   💡 This specific error usually means:")
        print("      1. boto3/botocore version is too old, OR")
        print("      2. The reference ARN is malformed/invalid, OR")
        print("      3. The reference doesn't exist")
    
    # Try to get more details
    if hasattr(e, 'response'):
        print()
        print("   Response details:")
        print(f"      {json.dumps(e.response, indent=6, default=str)}")

print()
print("=" * 60)
print("Debug complete!")
print("=" * 60)

