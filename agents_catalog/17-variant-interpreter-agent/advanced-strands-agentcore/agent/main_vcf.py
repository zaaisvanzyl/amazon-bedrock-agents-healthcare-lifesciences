"""
VCF Agent Main Entry Point
Updated to use simple VCF tables instead of deprecated HealthOmics stores
"""

from strands import Agent, tool
import argparse
import json
import os
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands.models import BedrockModel
from bedrock_agentcore_starter_toolkit import Runtime
from boto3.session import Session
import boto3

# Get region from environment or boto3 session
boto_session = Session()
region = os.environ.get('AWS_DEFAULT_REGION') or os.environ.get('AWS_REGION') or boto_session.region_name or 'us-east-1'

# Import VCF agent tools
try:
    from tools.vcf_agent_tools import vcf_agent_tools
    print("✅ Imported VCF agent tools")
except ImportError as e:
    print(f"⚠️  Warning: Could not import VCF tools: {e}")
    try:
        from agent.tools.vcf_agent_tools import vcf_agent_tools
        print("✅ Imported VCF agent tools (alternative path)")
    except ImportError:
        print("❌ Error: Could not import VCF agent tools from any path")
        vcf_agent_tools = []

# Define the model
bedrock_model = BedrockModel(
    model_id="anthropic.claude-3-sonnet-20240229-v1:0",
    region_name=region,
    temperature=0.1,
    streaming=False
)

# Define agent configuration
agent_name = "vcf-genomics-agent"
agent_description = "VCF genomics analysis agent for clinical variant interpretation"
agent_instruction = """You are an advanced genomics analysis assistant specialized in clinical variant interpretation using standard VCF (Variant Call Format) data.

Your primary focus is on clinically actionable genomic analysis with these specialized capabilities:

CORE CLINICAL TOOLS:
1. **Patient Count** (count_patients_in_cohort): Count patients/samples in the cohort
2. **Gene-Specific Analysis** (query_variants_by_gene): For targeted gene panels, cancer genes (BRCA1/2, TP53), pharmacogenes
3. **Chromosomal Analysis** (query_variants_by_chromosome): For chromosomal abnormalities, specific genomic regions
4. **Cohort Summary** (get_cohort_summary): Get comprehensive cohort statistics
5. **Quality Analysis** (analyze_high_quality_variants): Analyze high-quality PASS variants

CLINICAL DECISION SUPPORT:
- Always apply quality filtering (qual > 30 AND PASS filters when applicable)
- Prioritize variants by quality score and filter status
- Provide actionable clinical interpretations
- Include VEP consequence annotations from INFO field when available

TOOL SELECTION STRATEGY:
1. **For patient/sample counts**: Use count_patients_in_cohort (e.g., "How many patients?", "cohort size")
2. **For specific genes**: Use query_variants_by_gene (e.g., "BRCA1 variants", "TP53 mutations")
3. **For chromosomal regions**: Use query_variants_by_chromosome (e.g., "chromosome 17 variants")
4. **For cohort overview**: Use get_cohort_summary (e.g., "summarize the cohort", "overall statistics")
5. **For quality analysis**: Use analyze_high_quality_variants (e.g., "high quality variants", "PASS variants")

EXECUTION FLOW:
1. Understand the user query
2. Select the MOST APPROPRIATE single tool
3. Call the tool with proper parameters
4. Present the results clearly and concisely
5. Provide clinical interpretation when relevant

RESPONSE FORMAT:
- Start with a clear answer to the user's question
- Provide key statistics and metrics
- Include relevant variant details when appropriate
- Suggest follow-up analyses if helpful

Remember: Focus on clinically actionable insights that can inform patient care, genetic counseling, and treatment decisions.
"""

# Create the agent with VCF tools
try:
    vcf_agent = Agent(
        model=bedrock_model,
        system_prompt=agent_instruction,
        tools=vcf_agent_tools
    )
    print("✅ VCF agent created successfully")
except Exception as e:
    print(f"❌ Error creating VCF agent: {e}")
    vcf_agent = None

app = BedrockAgentCoreApp()

@app.entrypoint
async def strands_agent_bedrock_streaming(payload):
    """
    Invoke the agent with streaming capabilities
    """
    print(f"🔍 Entrypoint called with payload: {payload}")
    user_input = payload.get("prompt")
    print(f"🔍 User input: {user_input}")
    
    # Initial message
    yield "🧬 VCF Genomics Analysis Agent initialized. Processing your query...\n\n"
    
    if vcf_agent is None:
        print("❌ VCF agent is None!")
        yield "Error: VCF agent not initialized"
        return
    
    print("✅ VCF agent exists, starting stream...")
    
    try:
        tool_name = None
        event_count = 0
        async for event in vcf_agent.stream_async(user_input):
            event_count += 1
            print(f"🔍 Event {event_count}: {event.keys()}")
            
            if (
                "current_tool_use" in event
                and event["current_tool_use"].get("name") != tool_name
            ):
                tool_name = event["current_tool_use"]["name"]
                tool_msg = f"\n\n🔧 Using tool: {tool_name}\n\n"
                print(f"🔧 Tool use: {tool_name}")
                yield tool_msg
            
            if "data" in event:
                data = event["data"]
                print(f"📤 Yielding data: {data[:100] if len(data) > 100 else data}")
                yield data
        
        print(f"✅ Stream completed. Total events: {event_count}")
                
    except Exception as e:
        error_response = f"Error: {str(e)}"
        print(f"❌ Streaming error: {error_response}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        yield error_response

if __name__ == "__main__":
    print("=" * 80)
    print("🧬 VCF Genomics Agent - Ready")
    print("=" * 80)
    app.run()

