#!/usr/bin/env python3
"""
Deploy the fixed VCF agent to Bedrock AgentCore
"""

import boto3
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from bedrock_agentcore_starter_toolkit import Runtime

print("=" * 80)
print("🚀 Deploying Fixed VCF Agent to Bedrock AgentCore")
print("=" * 80)
print()

# Configuration
AGENT_NAME = "genomicsappvariant"
REGION = os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')

# Get IAM role
print("🔍 Getting IAM role...")
try:
    iam = boto3.client('iam')
    role = iam.get_role(RoleName='genomics-vep-pipeline-agent-role')
    execution_role = role['Role']['Arn']
    print(f"✅ IAM Role: {execution_role}")
except Exception as e:
    print(f"❌ Error getting IAM role: {e}")
    print()
    print("Create the role first:")
    print("  python3 scripts/create_agent_role.py")
    sys.exit(1)

print()

# Verify tools load correctly
print("🔍 Verifying agent tools...")
os.environ['VCF_TABLE_NAME'] = 'vcf_data'
os.environ['LAKE_FORMATION_DATABASE'] = 'genomics_agent_db2'

try:
    from agent.tools.vcf_agent_tools import vcf_agent_tools
    print(f"✅ {len(vcf_agent_tools)} tools verified:")
    for tool in vcf_agent_tools:
        print(f"   - {tool.__name__}")
except Exception as e:
    print(f"❌ Error loading tools: {e}")
    sys.exit(1)

print()

# Initialize runtime
print("📦 Initializing Bedrock AgentCore Runtime...")
agentcore_runtime = Runtime()

# Configure
print("⚙️  Configuring agent...")
try:
    response = agentcore_runtime.configure(
        entrypoint="agent/main.py",
        execution_role=execution_role,
        auto_create_ecr=True,
        requirements_file="agent/runtime_requirements.txt",
        region=REGION,
        agent_name=AGENT_NAME,
        disable_otel=False
    )
    print("✅ Configuration complete")
except Exception as e:
    print(f"❌ Configuration error: {e}")
    sys.exit(1)

print()

# Launch
print("🚀 Launching agent to Bedrock AgentCore...")
print("   This may take 2-5 minutes...")
print()

try:
    launch_result = agentcore_runtime.launch(
        auto_update_on_conflict=True
    )
    print("✅ Launch complete!")
    print()
    print(f"Agent Runtime ARN: {launch_result.get('agentRuntimeArn', 'N/A')}")
    print(f"Status: {launch_result.get('status', 'N/A')}")
except Exception as e:
    print(f"❌ Launch error: {e}")
    sys.exit(1)

print()
print("=" * 80)
print("✅ Deployment Successful!")
print("=" * 80)
print()
print("Next steps:")
print("  1. Wait 1-2 minutes for the runtime to be READY")
print("  2. Run: ./run_streamlit.sh")
print("  3. Ask: 'How many patients are in the present cohort?'")
print()
print("The agent will now use the correct VCF tools!")

