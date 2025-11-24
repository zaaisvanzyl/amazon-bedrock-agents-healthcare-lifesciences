

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

# Import VCF agent tools (updated for standard VCF tables, not deprecated HealthOmics)
# Import path differs based on whether we're running standalone or in container
try:
    from tools.vcf_agent_tools import vcf_agent_tools as genomics_store_agent_tools
    print("✅ Imported VCF agent tools from tools.vcf_agent_tools")
except ImportError:
    try:
        from agent.tools.vcf_agent_tools import vcf_agent_tools as genomics_store_agent_tools
        print("✅ Imported VCF agent tools from agent.tools.vcf_agent_tools")
    except ImportError:
        print("❌ ERROR: Could not import VCF agent tools!")
        # Fallback to old tools (will fail but shows error)
        from agent.tools.genomics_store_interpreters import genomics_store_agent_tools
        print("⚠️ WARNING: Using deprecated HealthOmics tools - will not work!")

# Define the model
bedrock_model = BedrockModel(
    model_id="anthropic.claude-3-sonnet-20240229-v1:0",  # Claude 3 Sonnet (verified accessible)
    region_name=region,
    temperature=0.1,
    streaming=True
)

# Define orchestrator agent configuration below
agent_name = "vcf-agent-direct"
agent_description = "VCF direct agent for clinical insights discovery"
agent_instruction = """You are an advanced genomics analysis assistant specialized in clinical variant interpretation using standard VCF (Variant Call Format) data.

Your primary focus is on clinically actionable genomic analysis with these specialized capabilities:

CORE CLINICAL TOOLS:
1. **Patient Count** (count_patients_in_cohort): Count patients/samples in the cohort - USE THIS for "how many patients" questions
2. **Position Lookup** (query_variant_at_position): FAST lookup for specific genomic positions - USE THIS for position-specific queries like "chr13:32332591"
3. **Gene-Specific Analysis** (query_variants_by_gene): For targeted gene panels, cancer genes (BRCA1/2, TP53), pharmacogenes
4. **Chromosomal Analysis** (query_variants_by_chromosome): For chromosomal abnormalities, specific genomic regions
5. **Cohort Summary** (get_cohort_summary): Get comprehensive cohort statistics and overview
6. **Quality Analysis** (analyze_high_quality_variants): Analyze high-quality PASS variants

CLINICAL DECISION SUPPORT:
- Always apply quality filtering (qual > 30 AND PASS filters when applicable)
- Prioritize variants by quality score and filter status
- Provide actionable clinical interpretations
- Include VEP consequence annotations from INFO field when available

TOOL SELECTION STRATEGY:
1. **For patient/sample counts**: ALWAYS use count_patients_in_cohort (e.g., "How many patients?", "cohort size", "number of samples")
2. **For specific positions**: ALWAYS use query_variant_at_position for position queries (e.g., "chr13:32332591", "variant at position 32332591")
3. **For specific genes with positions**: Use query_variant_at_position first if position given (e.g., "BRCA2 at chr13:32332591")
4. **For specific genes without positions**: Use query_variants_by_gene (e.g., "BRCA1 variants", "TP53 mutations")
5. **For chromosomal regions**: Use query_variants_by_chromosome (e.g., "chromosome 17 variants")
6. **For cohort overview**: Use get_cohort_summary (e.g., "summarize the cohort", "overall statistics")
7. **For quality analysis**: Use analyze_high_quality_variants (e.g., "high quality variants", "PASS variants")

EXECUTION FLOW:
1. Understand the user query
2. Select the MOST APPROPRIATE single tool
3. Call the tool with proper parameters
4. Present the results clearly and concisely
5. DO NOT call multiple tools unless user explicitly requests detailed analysis

CRITICAL: For "how many patients" questions, ALWAYS use count_patients_in_cohort tool first!

Remember: Focus on clinically actionable insights that can inform patient care, genetic counseling, and treatment decisions.
"""

# Create the direct agent with genomics tools
try:
    direct_agent = Agent(
        model=bedrock_model,
        system_prompt=agent_instruction,
        tools=genomics_store_agent_tools
    )
    print("✅ Direct agent created successfully")
except Exception as e:
    print(f"❌ Error creating direct agent: {e}")
    direct_agent = None

app = BedrockAgentCoreApp()

@app.entrypoint
async def strands_agent_bedrock_streaming(payload):
    """
    Invoke the agent with streaming capabilities
    """
    print(f"🔍 Entrypoint called with payload: {payload}")
    user_input = payload.get("prompt")
    print(f"🔍 User input: {user_input}")
    
    # Test yield to verify streaming works
    yield "Agent initialized. Processing query...\n\n"
    
    if direct_agent is None:
        print("❌ Direct agent is None!")
        yield "Error: Direct agent not initialized"
        return
    
    # Reset agent conversation state to prevent tool use ID conflicts
    # This ensures each query starts with a clean slate
    try:
        direct_agent.reset()
        print("✅ Agent conversation state reset")
    except AttributeError:
        # If reset() doesn't exist, try clearing the message history
        if hasattr(direct_agent, 'messages'):
            direct_agent.messages = []
            print("✅ Agent message history cleared")
    
    print("✅ Direct agent exists, starting stream...")
    
    try:
        tool_name = None
        event_count = 0
        async for event in direct_agent.stream_async(user_input):
            event_count += 1
            print(f"🔍 Event {event_count}: {event.keys()}")
            
            if (
                "current_tool_use" in event
                and event["current_tool_use"].get("name") != tool_name
            ):
                tool_name = event["current_tool_use"]["name"]
                tool_msg = f"\n\nUsing tool: {tool_name}\n\n"
                print(f"Tool use: {tool_name}")
                yield tool_msg
            
            if "data" in event:
                data = str(event["data"]) if event["data"] is not None else ""  # Ensure data is always a string
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
    app.run()
