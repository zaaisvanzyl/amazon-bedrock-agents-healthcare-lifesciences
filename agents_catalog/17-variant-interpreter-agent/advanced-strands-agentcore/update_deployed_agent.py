#!/usr/bin/env python3
"""
Update the deployed Bedrock AgentCore agent to use vcf_data_annotated table
"""
import os
import sys
import boto3
import json

# Set environment for annotated table
os.environ['VCF_TABLE_NAME'] = 'vcf_data_annotated'
os.environ['LAKE_FORMATION_DATABASE'] = 'genomics_agent_db2'
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'

REGION = 'us-east-1'
ACCOUNT_ID = '149536495426'
AGENT_RUNTIME_ID = 'genomicsappvariant'  # Your agent runtime ID

print("=" * 70)
print("🔄 Updating Deployed Agent to Use VEP-Annotated Data")
print("=" * 70)

# Initialize clients
agentcore = boto3.client('bedrock-agentcore-control', region_name=REGION)

try:
    # Get current agent runtime
    print("\n1️⃣  Fetching current agent runtime...")
    response = agentcore.get_agent_runtime(agentRuntimeId=AGENT_RUNTIME_ID)
    
    print(f"   ✅ Found agent: {response['agentRuntimeId']}")
    print(f"   Current status: {response['status']}")
    
    # Update environment variables in the agent configuration
    print("\n2️⃣  Updating agent environment variables...")
    
    # Update the agent runtime with new environment variables
    update_response = agentcore.update_agent_runtime(
        agentRuntimeId=AGENT_RUNTIME_ID,
        environmentVariables={
            'VCF_TABLE_NAME': 'vcf_data_annotated',
            'LAKE_FORMATION_DATABASE': 'genomics_agent_db2',
            'AWS_DEFAULT_REGION': 'us-east-1',
            'REGION': 'us-east-1',
            'ACCOUNT_ID': ACCOUNT_ID
        }
    )
    
    print(f"   ✅ Agent updated successfully!")
    print(f"   New version ARN: {update_response.get('agentRuntimeArn', 'N/A')}")
    
    print("\n" + "=" * 70)
    print("🎉 SUCCESS! Agent now uses vcf_data_annotated table")
    print("=" * 70)
    print("\n📋 Next Steps:")
    print("1. Wait ~1-2 minutes for the update to propagate")
    print("2. Refresh your Streamlit app")
    print("3. Test with: 'How many patients are in the cohort?'")
    print("4. Should see THOUSANDS of variants, not 4")
    print("=" * 70)
    
except agentcore.exceptions.ResourceNotFoundException:
    print(f"\n❌ Agent runtime '{AGENT_RUNTIME_ID}' not found")
    print("\n💡 Listing available agents:")
    
    try:
        list_response = agentcore.list_agent_runtimes(maxResults=10)
        for agent in list_response.get('agentRuntimes', []):
            print(f"   - {agent['agentRuntimeId']} (Status: {agent['status']})")
    except Exception as e:
        print(f"   ❌ Error listing agents: {e}")
        
except Exception as e:
    print(f"\n❌ Error updating agent: {e}")
    print(f"\n💡 Error type: {type(e).__name__}")
    
    # Try alternative: create a new version instead
    print("\n🔄 Trying alternative approach: Creating new agent version...")
    
    try:
        # Get the source code location
        source_response = agentcore.describe_agent_runtime(agentRuntimeId=AGENT_RUNTIME_ID)
        
        print("   Current agent details:")
        print(f"   - Runtime: {source_response.get('runtime', 'N/A')}")
        print(f"   - Source: {source_response.get('sourceType', 'N/A')}")
        
    except Exception as e2:
        print(f"   ❌ Could not describe agent: {e2}")
    
    sys.exit(1)

