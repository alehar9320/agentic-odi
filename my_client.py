import streamlit as st
import asyncio
import json
from openai import AsyncOpenAI
from fastmcp import Client

st.set_page_config(page_title="Agentic ODI Chat", page_icon="🚀", layout="wide")

st.title("Agentic ODI 🚀")
st.markdown("Chat with your ODI repository using a local LLM.")

# Configuration Sidebar
with st.sidebar:
    st.header("LLM Configuration")
    base_url = st.text_input("Base URL", value="http://localhost:11434/v1")
    api_key = st.text_input("API Key", value="ollama", type="password")
    model_name = st.text_input("Model Name", value="llama3.3-70b-versatile")
    mcp_url = st.text_input("MCP Server URL", value="http://localhost:8000/mcp")
    
    if st.button("Clear Chat"):
        st.session_state.messages = []
        st.rerun()

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Async helper to run MCP calls and OpenAI sync
async def handle_user_input(user_inp: str, system_prompt: str):
    # Initialize clients
    llm_client = AsyncOpenAI(base_url=base_url, api_key=api_key)
    mcp_client = Client(mcp_url)
    
    async with mcp_client:
        # 1. Fetch Tools from MCP
        mcp_tools = await mcp_client.list_tools()
        
        # Translate MCP tools to OpenAI tool format
        openai_tools = []
        for tool in mcp_tools:
            # fastmcp returns tools with name, description, parameters
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters if hasattr(tool, "parameters") else tool.inputSchema
                }
            })
            
        # 2. Add user message
        st.session_state.messages.append({"role": "user", "content": user_inp})
        
        # 3. Call LLM
        messages = [{"role": "system", "content": system_prompt}] + [
            {"role": m["role"], "content": m["content"]} for m in st.session_state.messages
        ]
        
        response = await llm_client.chat.completions.create(
            model=model_name,
            messages=messages,
            tools=openai_tools if openai_tools else None,
            tool_choice="auto" if openai_tools else "none"
        )
        
        message = response.choices[0].message
        
        # 4. Handle tool calls
        if message.tool_calls:
            messages.append(message) # Append assistant's tool call request
            st.session_state.messages.append({"role": "assistant", "content": f"🛠️ Calling tools: {', '.join([tc.function.name for tc in message.tool_calls])}"})
            
            for tool_call in message.tool_calls:
                func_name = tool_call.function.name
                func_args = json.loads(tool_call.function.arguments)
                
                # Execute against MCP server
                # In Streamlit, write status
                try:
                    tool_result = await mcp_client.call_tool(func_name, func_args)
                    result_str = str(tool_result)
                except Exception as e:
                    result_str = f"Error calling {func_name}: {str(e)}"
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": func_name,
                    "content": result_str
                })
                
            # Second LLM call with tool results
            final_response = await llm_client.chat.completions.create(
                model=model_name,
                messages=messages
            )
            final_content = final_response.choices[0].message.content
        else:
            final_content = message.content
            
        st.session_state.messages.append({"role": "assistant", "content": final_content})
        return final_content

if user_input := st.chat_input("Ask about or manage ODI data..."):
    # Immediately render user message
    with st.chat_message("user"):
        st.markdown(user_input)
        
    system_prompt = """You are Agentic ODI, an AI assistant helping a user manage their Outcome-Driven Innovation (ODI) repository.
    You have tools to add and query Jobs-to-be-Done, Steps, and Outcomes.
    When a user asks you to do something, use your tools. If they ask a general question, use your tools to retrieve context."""
    
    with st.spinner("Thinking..."):
        # Run async function in sync Streamlit context
        asyncio.run(handle_user_input(user_input, system_prompt))
    
    st.rerun()
