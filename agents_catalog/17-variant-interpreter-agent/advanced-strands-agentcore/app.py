import json
import re
import time
import uuid
from typing import Dict, Iterator, List

import boto3
import streamlit as st
from streamlit.logger import get_logger

logger = get_logger(__name__)
logger.setLevel("INFO")

# Page config
st.set_page_config(
    page_title="Genomics Variant Analysis Agent",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Minimal professional styling
st.markdown(
    """
    <style>
        /* Import clean modern font */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        
        /* Global styles - minimal and clean */
        * {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        }
        
        /* Hide Streamlit branding */
        .stAppDeployButton {display:none;}
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        
        /* Main app container - pure white */
        .main {
            background: #ffffff;
            padding: 2rem 3rem;
        }
        
        /* Sidebar - clean white with subtle border */
        [data-testid="stSidebar"] {
            background: #ffffff;
            border-right: 1px solid #e5e7eb;
            padding-top: 2rem;
        }
        
        [data-testid="stSidebar"] * {
            color: #1f2937 !important;
        }
        
        /* Sidebar buttons - minimal style */
        [data-testid="stSidebar"] .stButton button {
            background-color: #ffffff;
            border: 1px solid #d1d5db;
            color: #374151;
            border-radius: 6px;
            padding: 0.5rem 1rem;
            font-weight: 500;
            font-size: 0.875rem;
            transition: all 0.15s ease;
        }
        
        [data-testid="stSidebar"] .stButton button:hover {
            background-color: #f9fafb;
            border-color: #9ca3af;
        }
        
        [data-testid="stSidebar"] .stSelectbox select,
        [data-testid="stSidebar"] .stTextInput input {
            background-color: #ffffff;
            border: 1px solid #d1d5db;
            color: #1f2937;
            border-radius: 6px;
            font-size: 0.875rem;
        }
        
        /* Main title - clean and minimal */
        h1 {
            color: #111827;
            font-weight: 600;
            font-size: 2rem !important;
            margin-bottom: 0.5rem;
            letter-spacing: -0.025em;
        }
        
        /* Section headers */
        h2, h3 {
            color: #111827;
            font-weight: 600;
            margin-top: 1.5rem;
            letter-spacing: -0.025em;
        }
        
        h2 {
            font-size: 1.5rem !important;
        }
        
        h3 {
            font-size: 1.125rem !important;
        }
        
        h5 {
            color: #374151;
            font-size: 0.875rem !important;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.75rem;
        }
        
        /* Chat messages - clean cards */
        .stChatMessage {
            background: #ffffff;
            border-radius: 8px;
            padding: 1.25rem;
            margin: 0.75rem 0;
            border: 1px solid #e5e7eb;
            transition: border-color 0.15s ease;
        }
        
        .stChatMessage:hover {
            border-color: #d1d5db;
        }
        
        /* User message */
        [data-testid="stChatMessageContainer"] [data-testid="stChatMessage"]:has([aria-label="user"]) {
            background: #f9fafb;
            border-color: #e5e7eb;
        }
        
        /* Assistant message */
        [data-testid="stChatMessageContainer"] [data-testid="stChatMessage"]:has([aria-label="assistant"]) {
            background: #ffffff;
            border-color: #e5e7eb;
        }
        
        /* Chat input */
        .stChatInputContainer {
            border-top: 1px solid #e5e7eb;
            padding-top: 1rem;
            margin-top: 2rem;
        }
        
        .stChatInput textarea {
            border: 1px solid #d1d5db !important;
            border-radius: 8px !important;
            font-size: 0.9375rem;
        }
        
        .stChatInput textarea:focus {
            border-color: #6b7280 !important;
            box-shadow: none !important;
        }
        
        /* Buttons - minimal and clean */
        .stButton button {
            background: #111827;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 0.5rem 1rem;
            font-weight: 500;
            font-size: 0.875rem;
            transition: background 0.15s ease;
        }
        
        .stButton button:hover {
            background: #1f2937;
        }
        
        /* Secondary buttons */
        .stButton button[kind="secondary"] {
            background: #ffffff;
            color: #374151;
            border: 1px solid #d1d5db;
        }
        
        .stButton button[kind="secondary"]:hover {
            background: #f9fafb;
            border-color: #9ca3af;
        }
        
        /* Info boxes - minimal */
        .stAlert {
            border-radius: 6px;
            border: 1px solid #e5e7eb;
            background: #f9fafb;
            padding: 0.75rem 1rem;
        }
        
        .stSuccess {
            background: #f0fdf4;
            border-color: #86efac;
            color: #166534;
        }
        
        .stWarning {
            background: #fffbeb;
            border-color: #fcd34d;
            color: #92400e;
        }
        
        .stError {
            background: #fef2f2;
            border-color: #fca5a5;
            color: #991b1b;
        }
        
        .stInfo {
            background: #eff6ff;
            border-color: #93c5fd;
            color: #1e40af;
        }
        
        /* Expanders - minimal */
        .streamlit-expanderHeader {
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 6px;
            font-weight: 500;
            color: #374151;
            font-size: 0.875rem;
        }
        
        .streamlit-expanderHeader:hover {
            background: #f9fafb;
        }
        
        /* Code blocks */
        .stCodeBlock {
            border-radius: 6px;
            border: 1px solid #e5e7eb;
            background: #f9fafb;
        }
        
        code {
            background: #f3f4f6;
            padding: 0.125rem 0.25rem;
            border-radius: 3px;
            font-size: 0.875rem;
        }
        
        /* Containers with borders */
        [data-testid="stVerticalBlock"] > div[style*="border"] {
            border-radius: 8px !important;
            border: 1px solid #e5e7eb !important;
            padding: 1rem !important;
            background: #ffffff;
        }
        
        /* Checkbox styling */
        .stCheckbox {
            padding: 0.375rem 0;
        }
        
        .stCheckbox label {
            font-size: 0.875rem;
            color: #374151;
        }
        
        /* Caption text */
        .stCaption {
            color: #6b7280;
            font-size: 0.8125rem;
            font-weight: 400;
        }
        
        /* Divider */
        hr {
            margin: 1.5rem 0;
            border: none;
            height: 1px;
            background: #e5e7eb;
        }
        
        /* Sample question buttons in sidebar */
        [data-testid="stSidebar"] .stButton button[kind="secondary"] {
            text-align: left;
            justify-content: flex-start;
            padding: 0.625rem 0.875rem;
            font-size: 0.8125rem;
            white-space: normal;
            height: auto;
            line-height: 1.4;
            font-weight: 400;
        }
        
        /* Input fields */
        input, textarea, select {
            font-size: 0.875rem !important;
        }
        
        /* Layout and spacing */
        .block-container {
            padding-top: 2rem;
            padding-bottom: 3rem;
            max-width: 1200px;
        }
        
        /* Clean scrollbars */
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }
        
        ::-webkit-scrollbar-track {
            background: #f1f5f9;
        }
        
        ::-webkit-scrollbar-thumb {
            background: #cbd5e1;
            border-radius: 4px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: #94a3b8;
        }
        
        /* Markdown text */
        .stMarkdown {
            font-size: 0.9375rem;
            line-height: 1.6;
            color: #374151;
        }
        
        /* Links */
        a {
            color: #2563eb;
            text-decoration: none;
        }
        
        a:hover {
            text-decoration: underline;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

HUMAN_AVATAR = "👤"
AI_AVATAR = "⚡️"


def recursively_stringify(obj):
    """
    REMOVED - This was corrupting data by converting numbers to strings too early.
    The agent needs integers to format its responses correctly.
    """
    # Just return the object as-is - no conversion
    return obj


def fetch_agent_runtimes(region: str = "us-east-1") -> List[Dict]:
    """Fetch available agent runtimes from bedrock-agentcore-control"""
    try:
        client = boto3.client("bedrock-agentcore-control", region_name=region)
        response = client.list_agent_runtimes(maxResults=100)

        # Filter only READY agents and sort by name
        ready_agents = [
            agent
            for agent in response.get("agentRuntimes", [])
            if agent.get("status") == "READY"
        ]

        # Sort by most recent update time (newest first)
        ready_agents.sort(key=lambda x: x.get("lastUpdatedAt", ""), reverse=True)

        return ready_agents
    except Exception as e:
        st.error(f"Error fetching agent runtimes: {e}")
        return []


def fetch_agent_runtime_versions(
    agent_runtime_id: str, region: str = "us-east-1"
) -> List[Dict]:
    """Fetch versions for a specific agent runtime"""
    try:
        client = boto3.client("bedrock-agentcore-control", region_name=region)
        response = client.list_agent_runtime_versions(agentRuntimeId=agent_runtime_id)

        # Filter only READY versions
        ready_versions = [
            version
            for version in response.get("agentRuntimes", [])
            if version.get("status") == "READY"
        ]

        # Sort by most recent update time (newest first)
        ready_versions.sort(key=lambda x: x.get("lastUpdatedAt", ""), reverse=True)

        return ready_versions
    except Exception as e:
        st.error(f"Error fetching agent runtime versions: {e}")
        return []


def extract_tool_responses_from_content(content: str) -> List[str]:
    """Extract tool responses from the content"""
    tool_responses = []
    
    # Split content by tool usage markers
    if "Using tool:" in content:
        sections = content.split("Using tool:")
        
        for i, section in enumerate(sections[1:], 1):  # Skip first section (before any tool)
            # Extract tool name
            lines = section.split('\n')
            tool_name = lines[0].strip() if lines else f"Tool {i}"
            
            # Look for structured data patterns after tool usage
            # This could be JSON, formatted text, or other structured output
            tool_output = ""
            capturing = False
            
            for line in lines[1:]:
                # Stop capturing when we hit the next response text
                if any(phrase in line.lower() for phrase in ['based on', 'the results show', 'analysis reveals']):
                    break
                    
                # Look for structured data indicators
                if any(indicator in line for indicator in ['{', 'Total', 'Count:', 'Results:', '|', 'Error:']):
                    capturing = True
                
                if capturing:
                    tool_output += line + '\n'
                    
                # Stop if we hit empty lines after capturing started
                if capturing and line.strip() == "":
                    break
            
            if tool_output.strip():
                tool_responses.append(f"Tool: {tool_name}\n{tool_output.strip()}")
    
    return tool_responses


def clean_response_text(text: str, show_thinking: bool = True) -> str:
    """Clean and format response text for better presentation"""
    # Ensure text is always a string
    if text is None:
        return ""
    text = str(text)
    
    if not text:
        return text

    # Handle the consecutive quoted chunks pattern
    # Pattern: "word1" "word2" "word3" -> word1 word2 word3
    text = re.sub(r'"\s*"', "", text)
    text = re.sub(r'^"', "", text)
    text = re.sub(r'"$', "", text)

    # Replace literal \n with actual newlines
    text = text.replace("\\n", "\n")

    # Replace literal \t with actual tabs
    text = text.replace("\\t", "\t")

    # Clean up multiple spaces
    text = re.sub(r" {3,}", " ", text)

    # Fix newlines that got converted to spaces
    text = text.replace(" \n ", "\n")
    text = text.replace("\n ", "\n")
    text = text.replace(" \n", "\n")

    # Handle numbered lists
    text = re.sub(r"\n(\d+)\.\s+", r"\n\1. ", text)
    text = re.sub(r"^(\d+)\.\s+", r"\1. ", text)

    # Handle bullet points
    text = re.sub(r"\n-\s+", r"\n- ", text)
    text = re.sub(r"^-\s+", r"- ", text)

    # Handle section headers
    text = re.sub(r"\n([A-Za-z][A-Za-z\s]{2,30}):\s*\n", r"\n**\1:**\n\n", text)

    # Clean up multiple newlines
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Clean up thinking
    if not show_thinking:
        text = re.sub(r"<thinking>.*?</thinking>", "", text)

    return text.strip()


def extract_text_from_response(data) -> str:
    """Extract text content from response data in various formats"""
    if isinstance(data, dict):
        # Handle format: {'role': 'assistant', 'content': [{'text': 'Hello!'}]}
        if "role" in data and "content" in data:
            content = data["content"]
            if isinstance(content, list) and len(content) > 0:
                if isinstance(content[0], dict) and "text" in content[0]:
                    return str(content[0]["text"])
                else:
                    return str(content[0])
            elif isinstance(content, str):
                return content
            else:
                return str(content)

        # Handle other common formats
        if "text" in data:
            return str(data["text"])
        elif "content" in data:
            content = data["content"]
            if isinstance(content, str):
                return content
            else:
                return str(content)
        elif "message" in data:
            return str(data["message"])
        elif "response" in data:
            return str(data["response"])
        elif "result" in data:
            return str(data["result"])

    return str(data)
def parse_streaming_chunk(chunk: str) -> str:
    """Parse individual streaming chunk and extract meaningful content"""
    logger.debug(f"parse_streaming_chunk: received chunk: {chunk}")
    logger.debug(f"parse_streaming_chunk: chunk type: {type(chunk)}")

    try:
        # Try to parse as JSON first
        if chunk.strip().startswith("{"):
            logger.debug("parse_streaming_chunk: Attempting JSON parse")
            data = json.loads(chunk)
            logger.debug(f"parse_streaming_chunk: Successfully parsed JSON: {data}")

            # Handle the specific format: {'role': 'assistant', 'content': [{'text': '...'}]}
            if isinstance(data, dict) and "role" in data and "content" in data:
                content = data["content"]
                if isinstance(content, list) and len(content) > 0:
                    first_item = content[0]
                    if isinstance(first_item, dict) and "text" in first_item:
                        extracted_text = first_item["text"]
                        logger.debug(
                            f"parse_streaming_chunk: Extracted text: {extracted_text}"
                        )
                        return extracted_text
                    else:
                        return str(first_item)
                else:
                    return str(content)
            else:
                # Use the general extraction function for other formats
                return extract_text_from_response(data)

        # If not JSON, return the chunk as-is
        logger.debug("parse_streaming_chunk: Not JSON, returning as-is")
        return chunk
    except json.JSONDecodeError as e:
        logger.error(f"parse_streaming_chunk: JSON decode error: {e}")

        # Try to handle Python dict string representation (with single quotes)
        if chunk.strip().startswith("{") and "'" in chunk:
            logger.debug(
                "parse_streaming_chunk: Attempting to handle Python dict string"
            )
            try:
                # Try to convert single quotes to double quotes for JSON parsing
                # This is a simple approach - might need refinement for complex cases
                json_chunk = chunk.replace("'", '"')
                data = json.loads(json_chunk)
                logger.debug(
                    f"parse_streaming_chunk: Successfully converted and parsed: {data}"
                )

                # Handle the specific format
                if isinstance(data, dict) and "role" in data and "content" in data:
                    content = data["content"]
                    if isinstance(content, list) and len(content) > 0:
                        first_item = content[0]
                        if isinstance(first_item, dict) and "text" in first_item:
                            extracted_text = first_item["text"]
                            logger.debug(
                                f"parse_streaming_chunk: Extracted text from converted dict: {extracted_text}"
                            )
                            return extracted_text
                        else:
                            return str(first_item)
                    else:
                        return str(content)
                else:
                    return extract_text_from_response(data)
            except json.JSONDecodeError:
                logger.debug(
                    "parse_streaming_chunk: Failed to convert Python dict string"
                )
                pass

        # If all parsing fails, return the chunk as-is
        logger.debug("parse_streaming_chunk: All parsing failed, returning chunk as-is")
        return chunk


def invoke_agent_streaming(
    prompt: str,
    agent_arn: str,
    runtime_session_id: str,
    region: str = "us-east-1",
    show_tool: bool = True,
) -> Iterator[Dict]:
    """Invoke agent and yield streaming response chunks with tool tracking"""
    try:
        from botocore.config import Config
        config = Config(
            region_name=region,
            retries={'max_attempts': 3, 'mode': 'adaptive'},
            read_timeout=900,
            connect_timeout=180
        )
        agentcore_client = boto3.client("bedrock-agentcore", config=config)

        boto3_response = agentcore_client.invoke_agent_runtime(
            agentRuntimeArn=agent_arn,
            qualifier="DEFAULT",
            runtimeSessionId=runtime_session_id,
            payload=json.dumps({"prompt": prompt}),
        )

        logger.debug(f"contentType: {boto3_response.get('contentType', 'NOT_FOUND')}")

        if "text/event-stream" in boto3_response.get("contentType", ""):
            logger.debug("Using streaming response path")
            for line in boto3_response["response"].iter_lines(chunk_size=1):
                if line:
                    line = line.decode("utf-8")
                    logger.debug(f"Raw line: {line}")

                    if line.startswith("data: "):
                        line = line[6:].strip()
                        if not line:  # Skip empty lines
                            continue
                        try:
                            data = json.loads(line)
                            # Only double parse if data is a string
                            if isinstance(data, str):
                                data = json.loads(data)

                            # CRITICAL FIX: Check if data is a dict before checking for keys
                            if not isinstance(data, dict):
                                # If data is not a dict (e.g., it's an int, str, etc.), just yield it as text
                                logger.warning(f"Received non-dict data: type={type(data)}, value={data}")
                                yield {"type": "text", "content": str(data)}
                                continue
                            
                            # Parse each chunk and display only what is relevant
                            if "data" in data:
                                # Pass through the data as-is - the agent already formatted it correctly
                                content = data.get("data", "")
                                # Log what we're getting
                                logger.info(f"Stream data type: {type(content)}, value: {repr(content)[:200]}")
                                # Only convert to string if it's not already a string
                                if not isinstance(content, str):
                                    content = str(content)
                                yield {"type": "text", "content": content}
                            elif "current_tool_use" in data:
                                tool_name = data["current_tool_use"]["name"]
                                tool_input = data["current_tool_use"]["input"]
                                logger.debug(f"TOOL NAME: {tool_name}")
                                logger.debug(f"TOOL INPUT: {tool_input}")
                                if show_tool:
                                    yield {"type": "tool_use", "name": tool_name, "input": tool_input}
                            elif "message" in data:
                                if "content" in data["message"]:
                                    for obj in data["message"]["content"]:
                                        if "toolResult" in obj:
                                            tool_result = str(obj["toolResult"]["content"][0]["text"])  # Ensure it's a string
                                            logger.debug(f"TOOL RESULT: {tool_result}")
                                            yield {"type": "tool_result", "content": tool_result}
                        except json.JSONDecodeError as e:
                            logger.error(f"JSON decode error: {e}")
                            # Fallback to old parsing method
                            try:
                                parsed_chunk = parse_streaming_chunk(line)
                                # Ensure parsed_chunk is a string
                                if not isinstance(parsed_chunk, str):
                                    parsed_chunk = str(parsed_chunk)
                                
                                if parsed_chunk.strip():
                                    # Check if this chunk contains tool usage info
                                    if "Using tool:" in parsed_chunk:
                                        # Extract tool name
                                        import re
                                        tool_match = re.search(r'Using tool: (\w+)', parsed_chunk)
                                        if tool_match and show_tool:
                                            yield {"type": "tool_use", "name": tool_match.group(1), "input": "See agent response"}
                                    yield {"type": "text", "content": parsed_chunk}
                            except TypeError as te:
                                logger.error(f"TypeError in fallback parsing: {te}, line was: {line}, parsed_chunk type: {type(parsed_chunk) if 'parsed_chunk' in locals() else 'not set'}")
                                # Yield a safe error message
                                yield {"type": "text", "content": f"[Parsing error: {str(te)}]"}
                    else:
                        logger.debug(f"Line doesn't start with 'data: ', skipping: {line}")
        else:
            # Handle non-streaming response (existing logic)
            response_obj = boto3_response.get("response")
            if hasattr(response_obj, "read"):
                content = response_obj.read()
                if isinstance(content, bytes):
                    content = content.decode("utf-8")
                try:
                    response_data = json.loads(content)
                    if isinstance(response_data, dict):
                        if "result" in response_data:
                            actual_data = response_data["result"]
                        else:
                            actual_data = response_data
                        
                        if "role" in actual_data and "content" in actual_data:
                            content_list = actual_data["content"]
                            if isinstance(content_list, list) and len(content_list) > 0:
                                first_item = content_list[0]
                                if isinstance(first_item, dict) and "text" in first_item:
                                    yield {"type": "text", "content": first_item["text"]}
                                else:
                                    yield {"type": "text", "content": str(first_item)}
                            else:
                                yield {"type": "text", "content": str(content_list)}
                        else:
                            text = extract_text_from_response(actual_data)
                            yield {"type": "text", "content": text}
                    else:
                        yield {"type": "text", "content": str(response_data)}
                except json.JSONDecodeError:
                    yield {"type": "text", "content": content}

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"CRITICAL ERROR in invoke_agent_streaming: {e}")
        logger.error(f"Full traceback:\n{error_details}")
        print(f"[CRITICAL ERROR] {e}")
        print(f"[TRACEBACK]\n{error_details}")
        yield {"type": "text", "content": f"Error invoking agent: {e}"}


def main():
    # Clean minimal header
    st.markdown(
        """
        <div style="margin-bottom: 3rem;">
            <h1 style="margin-bottom: 0.5rem; font-weight: 600; color: #111827;">Genomics Variant Analysis</h1>
            <p style="color: #6b7280; font-size: 0.9375rem; font-weight: 400; margin: 0;">
                Instantly find clinical and scientific evidence for genes or variants with AI
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Sidebar for settings
    with st.sidebar:
        # Region selection (moved up since it affects agent fetching)
        st.markdown("##### AWS Region")
        region = st.selectbox(
            "AWS Region",
            ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"],
            index=0,
            label_visibility="collapsed",
        )

        # Agent selection - hardcoded for genomics agent
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("##### Agent Configuration")
        
        # Use the specific genomics agent with VEP-annotated data
        agent_arn = "arn:aws:bedrock-agentcore:us-east-1:149536495426:runtime/main-U0xw41D5VF"
        
        st.markdown(
            f"""
            <div style="background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 6px; padding: 0.75rem; margin-bottom: 1rem;">
                <div style="font-size: 0.75rem; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.25rem;">Active Agent</div>
                <div style="font-size: 0.875rem; color: #111827; font-weight: 500;">genomicsapp_vcf_agent_supervisor</div>
                <div style="font-size: 0.8125rem; color: #6b7280; margin-top: 0.25rem;">{region}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        with st.expander("View ARN", expanded=False):
            st.code(agent_arn, language="text")
        if st.button("Refresh Agent", key="refresh_agents", help="Refresh agent list", use_container_width=True):
            st.rerun()

        # Runtime Session ID
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("##### Session")

        # Initialize session ID in session state if not exists
        if "runtime_session_id" not in st.session_state:
            st.session_state.runtime_session_id = str(uuid.uuid4())

        # Session ID input with generate button
        runtime_session_id = st.text_input(
            "Session ID",
            value=st.session_state.runtime_session_id,
            help="Unique identifier for this runtime session",
        )

        if st.button("New Session", help="Generate new session ID and clear chat", use_container_width=True):
            st.session_state.runtime_session_id = str(uuid.uuid4())
            st.session_state.messages = []  # Clear chat messages when resetting session
            st.rerun()

        # Update session state if user manually changed the ID
        if runtime_session_id != st.session_state.runtime_session_id:
            st.session_state.runtime_session_id = runtime_session_id

        # Response formatting options
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("##### Display Options")
        auto_format = st.checkbox(
            "Auto-format responses",
            value=False,  # DISABLED - Was corrupting numbers
            help="Automatically clean and format responses",
        )
        show_raw = st.checkbox(
            "Show raw response",
            value=False,
            help="Display the raw unprocessed response",
        )
        show_tools = st.checkbox(
            "Show tools",
            value=True,
            help="Display tools used",
        )
        show_thinking = st.checkbox(
            "Show thinking",
            value=False,
            help="Display the AI thinking text",
        )

        # Clear chat button
        if st.button("Clear Chat", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

        # Sample questions
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("##### Example Queries")
        
        sample_questions = [
            "How many patients are in the present cohort?",
            "Analyze chromosome 17 variants in patient NA21135",
            "What's the frequency of chr13:32332591 in BRCA2 variant?",
            "Check variants for BRCA family in patient NA21135",
            "Analyze patient NA21135 for risk stratification",
            "Major drug related variant pathways in cohort",
            "Heart disease genomic aberrations in NA21135",
            "Comprehensive clinical summary of cohort"
        ]
        
        for i, question in enumerate(sample_questions):
            if st.button(question, key=f"sample_{i}", use_container_width=True):
                st.session_state["selected_question"] = question

        # Connection status
        st.markdown("<br>", unsafe_allow_html=True)
        if agent_arn:
            st.markdown(
                '<div style="padding: 0.5rem; background: #f0fdf4; border: 1px solid #86efac; border-radius: 6px; font-size: 0.8125rem; color: #166534; text-align: center;">Agent Connected</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div style="padding: 0.5rem; background: #fef2f2; border: 1px solid #fca5a5; border-radius: 6px; font-size: 0.8125rem; color: #991b1b; text-align: center;">No Agent Selected</div>',
                unsafe_allow_html=True,
            )
    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat messages
    for i, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"], avatar=message["avatar"]):
            st.markdown(message["content"])
            # Show elapsed time for assistant messages
            if message["role"] == "assistant" and "elapsed" in message:
                st.caption(f"Response time: {message['elapsed']:.2f}s")
                
                # Show model execution logs for all assistant messages
                with st.expander("Execution Details"):
                    formatted_content = message["content"]
                    
                    # Extract explicit tool usage first
                    explicit_tools = []
                    if "Using tool:" in formatted_content:
                        tool_sections = formatted_content.split("Using tool:")
                        for j, section in enumerate(tool_sections[1:], 1):
                            tool_name = section.split('\n')[0].strip()
                            explicit_tools.append(f"**Tool {j}:** {tool_name}")
                    
                    if "Tool input:" in formatted_content:
                        input_sections = formatted_content.split("📝 Tool input:")
                        for j, section in enumerate(input_sections[1:], 1):
                            input_part = section.split('...')[0].strip()
                            if input_part:
                                st.code(f"Tool Input {j}: {input_part}", language="json")
                    
                    # Show raw tool responses if available
                    if "tool_responses" in message and message["tool_responses"]:
                        st.markdown("**🔧 Raw Tool Responses:**")
                        for j, tool_response in enumerate(message["tool_responses"], 1):
                            with st.expander(f"Tool Response {j}"):
                                st.code(tool_response, language="text")
                    else:
                        # If no tool responses captured, show a message
                        if "Using tool:" in formatted_content:
                            st.info("**Note:** Tool was executed but raw response not captured in streaming. The agent processed the tool output and provided the summary above.")
                    
                    # Only show inferred execution if no explicit tools found
                    if not explicit_tools:
                        execution_info = []
                        content_lower = formatted_content.lower()
                        
                        # More specific keyword detection
                        if "query" in content_lower and ("database" in content_lower or "genomics" in content_lower):
                            execution_info.append("🔍 **Database Query Executed**")
                        if "analy" in content_lower and ("variant" in content_lower or "chromosome" in content_lower):
                            execution_info.append("📊 **Genomic Analysis Performed**")
                        if "chromosome" in content_lower and ("variant" in content_lower):
                            execution_info.append("🔬 **Chromosome-specific Processing**")
                        if ("patient" in content_lower or "sample" in content_lower) and "cohort" in content_lower:
                            execution_info.append("👤 **Cohort Data Processing**")
                        
                        # Display execution summary only if we have meaningful steps
                        if execution_info:
                            st.markdown("**Inferred Execution Steps:**")
                            for info in execution_info:
                                st.markdown(f"- {info}")
                    else:
                        # Show explicit tools
                        st.markdown("**Explicit Tool Usage:**")
                        for tool in explicit_tools:
                            st.info(tool)
                    
                    # Show processing time analysis
                    if "elapsed" in message:
                        processing_time = message["elapsed"]
                        if processing_time > 60:
                            st.error(f"🐌 Very slow: {processing_time:.1f}s - Large dataset processing")
                        elif processing_time > 30:
                            st.warning(f"⚠️ Complex analysis: {processing_time:.1f}s")
                        elif processing_time > 15:
                            st.info(f"ℹ️ Standard processing: {processing_time:.1f}s")
                        else:
                            st.success(f"✅ Quick response: {processing_time:.1f}s")
                    
                    # Show captured chunks for debugging
                    if "chunks" in message and message["chunks"]:
                        chunks = message["chunks"]
                        st.markdown(f"**Streaming Info:** {len(chunks)} chunks received")
                        
                        if st.checkbox("Show AgentCore Chunks", key=f"chunks_{i}"):
                            st.markdown("**Raw Streaming Chunks:**")
                            for j, chunk in enumerate(chunks[:10]):  # Show max 10 chunks
                                with st.expander(f"Chunk {j+1}"):
                                    try:
                                        # Try to parse as JSON
                                        import json
                                        if isinstance(chunk, str) and (chunk.strip().startswith('{') or chunk.strip().startswith('[')):
                                            parsed = json.loads(chunk)
                                            st.json(parsed)
                                        else:
                                            st.code(str(chunk), language="text")
                                    except:
                                        st.code(str(chunk), language="text")
                            
                            if len(chunks) > 10:
                                st.info(f"... and {len(chunks) - 10} more chunks")

    # Handle sample question selection
    if "selected_question" in st.session_state:
        prompt = st.session_state["selected_question"]
        del st.session_state["selected_question"]
        
        # Process the selected question
        if not agent_arn:
            st.error("Please select an agent in the sidebar first.")
        else:
            # Add user message to chat history
            st.session_state.messages.append(
                {"role": "user", "content": prompt, "avatar": HUMAN_AVATAR}
            )
            with st.chat_message("user", avatar=HUMAN_AVATAR):
                st.markdown(prompt)

            # Generate assistant response
            with st.chat_message("assistant", avatar=AI_AVATAR):
                message_placeholder = st.empty()
                start_time = time.time()  # Start timing
                chunk_buffer = ""

                try:
                    # Stream the response
                    captured_chunks = []
                    tool_responses = []
                    for chunk_data in invoke_agent_streaming(
                        prompt,
                        agent_arn,
                        st.session_state.runtime_session_id,
                        region,
                        show_tools,
                    ):
                        captured_chunks.append(chunk_data)
                        
                        if chunk_data["type"] == "text":
                            chunk = chunk_data["content"]
                            # CRITICAL: Log the exact chunk we received
                            print(f"[CHUNK] Type: {type(chunk)}, Value: {repr(chunk)}")
                            if not isinstance(chunk, str):
                                print(f"[CHUNK] Converting {type(chunk)} to string")
                                chunk = str(chunk)
                            
                            # FIX: Strip surrounding quotes that Bedrock AgentCore adds
                            # The chunks come as '"text"' instead of 'text'
                            if chunk.startswith('"') and chunk.endswith('"'):
                                chunk = chunk[1:-1]
                                print(f"[CHUNK] After stripping quotes: {repr(chunk)}")
                            
                            # Unescape literal \n and \t
                            chunk = chunk.replace('\\n', '\n').replace('\\t', '\t')
                        
                            chunk_buffer += chunk
                            print(f"[BUFFER] Length: {len(chunk_buffer)}, Last 100 chars: {repr(chunk_buffer[-100:])}")
                        
                            # Update display for every text chunk
                            if auto_format:
                                cleaned_response = clean_response_text(chunk_buffer, show_thinking)
                                message_placeholder.markdown(cleaned_response + " ▌")
                            else:
                                message_placeholder.markdown(chunk_buffer + " ▌")
                        
                        elif chunk_data["type"] == "tool_use" and show_tools:
                            container = st.container(border=True)
                            container.markdown(f"**Tool: {chunk_data['name']}**")
                            with container.expander("View input", expanded=False):
                                st.code(str(chunk_data['input']), language="json")
                        
                        elif chunk_data["type"] == "tool_result":
                            tool_responses.append(chunk_data["content"])
                            if show_tools:
                                container = st.container(border=True)
                                container.markdown("**Tool Result**")
                                container.code(chunk_data["content"], language="text")

                        time.sleep(0.01)  # nosemgrep: arbitrary-sleep

                    # Calculate elapsed time
                    elapsed = time.time() - start_time

                    # Final response without cursor
                    if auto_format:
                        full_response = clean_response_text(chunk_buffer, show_thinking)
                    else:
                        full_response = chunk_buffer

                    # Try to extract tool results from the complete response
                    if "Using tool:" in chunk_buffer and not tool_responses:
                        # Look for the actual tool output in the agent's response
                        # This is a workaround since the streaming doesn't provide raw tool results
                        import re
                        
                        # Look for patterns that indicate tool results
                        patterns = [
                            r'Based on.*?results.*?(\d+.*?)(?:\.|$)',
                            r'The query.*?shows.*?(\d+.*?)(?:\.|$)',
                            r'Analysis.*?reveals.*?(\d+.*?)(?:\.|$)',
                        ]
                        
                        for pattern in patterns:
                            match = re.search(pattern, chunk_buffer, re.IGNORECASE | re.DOTALL)
                            if match:
                                result = match.group(1).strip()
                                # Clean up markdown formatting
                                result = re.sub(r'\*\*', '', result)
                                tool_responses.append(f"Extracted result: {result}")
                                break
                        
                        # If no pattern matched, add a generic message
                        if not tool_responses:
                            tool_responses.append("Tool executed successfully - see agent response for results")

                    message_placeholder.markdown(full_response)
                    
                    # Show response time
                    st.caption(f"Response time: {elapsed:.2f}s")

                    # Show raw response in expander if requested
                    if show_raw:
                        with st.expander("View raw response"):
                            st.text(chunk_buffer)

                except Exception as e:
                    elapsed = time.time() - start_time
                    error_msg = f"❌ **Error:** {str(e)}"
                    message_placeholder.markdown(error_msg)
                    full_response = error_msg

            # Add assistant response to chat history
            st.session_state.messages.append(
                {"role": "assistant", "content": full_response, "avatar": AI_AVATAR, "elapsed": elapsed, "raw_content": chunk_buffer, "chunks": captured_chunks, "tool_responses": tool_responses}
            )
            st.rerun()

    # Chat input
    if prompt := st.chat_input("Ask about variants, genes, or patient cohorts..."):
        if not agent_arn:
            st.error("Please select an agent in the sidebar first.")
            return

        # Add user message to chat history
        st.session_state.messages.append(
            {"role": "user", "content": prompt, "avatar": HUMAN_AVATAR}
        )
        with st.chat_message("user", avatar=HUMAN_AVATAR):
            st.markdown(prompt)

        # Generate assistant response
        with st.chat_message("assistant", avatar=AI_AVATAR):
            message_placeholder = st.empty()
            start_time = time.time()  # Start timing
            chunk_buffer = ""
            tool_responses = []  # Initialize tool_responses

            try:
                # Stream the response
                captured_chunks = []
                tool_responses = []
                for chunk_data in invoke_agent_streaming(
                    prompt,
                    agent_arn,
                    st.session_state.runtime_session_id,
                    region,
                    show_tools,
                ):
                    captured_chunks.append(chunk_data)
                    
                    if chunk_data["type"] == "text":
                        chunk = chunk_data["content"]
                        # CRITICAL: Log the exact chunk we received
                        print(f"[CHUNK] Type: {type(chunk)}, Value: {repr(chunk)}")
                        logger.debug(f"MAIN LOOP: chunk type: {type(chunk)}")
                        logger.debug(f"MAIN LOOP: chunk content: {chunk}")

                        if not isinstance(chunk, str):
                            print(f"[CHUNK] Converting {type(chunk)} to string")
                            chunk = str(chunk)
                        
                        # FIX: Strip surrounding quotes that Bedrock AgentCore adds
                        # The chunks come as '"text"' instead of 'text'
                        if chunk.startswith('"') and chunk.endswith('"'):
                            chunk = chunk[1:-1]
                            print(f"[CHUNK] After stripping quotes: {repr(chunk)}")
                        
                        # Unescape literal \n and \t
                        chunk = chunk.replace('\\n', '\n').replace('\\t', '\t')

                        chunk_buffer += chunk
                        print(f"[BUFFER] Length: {len(chunk_buffer)}, Last 100 chars: {repr(chunk_buffer[-100:])}")

                        # Update display for every text chunk
                        if auto_format:
                            cleaned_response = clean_response_text(chunk_buffer, show_thinking)
                            message_placeholder.markdown(cleaned_response + " ▌")
                        else:
                            message_placeholder.markdown(chunk_buffer + " ▌")
                    
                    elif chunk_data["type"] == "tool_use" and show_tools:
                        container = st.container(border=True)
                        container.markdown(f"**Tool: {chunk_data['name']}**")
                        with container.expander("View input", expanded=False):
                            st.code(str(chunk_data['input']), language="json")
                    
                    elif chunk_data["type"] == "tool_result":
                        tool_responses.append(chunk_data["content"])
                        if show_tools:
                            container = st.container(border=True)
                            container.markdown("**Tool Result**")
                            container.code(chunk_data["content"], language="text")

                    time.sleep(0.01)  # nosemgrep: arbitrary-sleep

                # Calculate elapsed time
                elapsed = time.time() - start_time

                # Final response without cursor
                if auto_format:
                    full_response = clean_response_text(chunk_buffer, show_thinking)
                else:
                    full_response = chunk_buffer

                # Try to extract tool results from the complete response
                chunk_buffer = str(chunk_buffer) if chunk_buffer is not None else ""  # Extra safety
                if "Using tool:" in chunk_buffer and not tool_responses:
                    # Look for the actual tool output in the agent's response
                    import re
                    
                    # Look for patterns that indicate tool results
                    patterns = [
                        r'Based on.*?results.*?(\d+.*?)(?:\.|$)',
                        r'The query.*?shows.*?(\d+.*?)(?:\.|$)', 
                        r'Analysis.*?reveals.*?(\d+.*?)(?:\.|$)',
                    ]
                    
                    for pattern in patterns:
                        match = re.search(pattern, chunk_buffer, re.IGNORECASE | re.DOTALL)
                        if match:
                            result = match.group(1).strip()
                            # Clean up markdown formatting  
                            result = re.sub(r'\*\*', '', result)
                            tool_responses.append(f"Extracted result: {result}")
                            break
                    
                    # If no pattern matched, add a generic message
                    if not tool_responses:
                        tool_responses.append("Tool executed successfully - see agent response for results")

                message_placeholder.markdown(full_response)
                
                # Show response time
                st.caption(f"Response time: {elapsed:.2f}s")

                # Show raw response in expander if requested
                if show_raw:
                    with st.expander("View raw response"):
                        st.text(chunk_buffer)

            except Exception as e:
                elapsed = time.time() - start_time
                error_msg = f"❌ **Error:** {str(e)}"
                message_placeholder.markdown(error_msg)
                full_response = error_msg

        # Add assistant response to chat history
        st.session_state.messages.append(
            {"role": "assistant", "content": full_response, "avatar": AI_AVATAR, "elapsed": elapsed, "raw_content": chunk_buffer, "chunks": captured_chunks, "tool_responses": tool_responses}
        )


if __name__ == "__main__":
    main()
