import streamlit as st
import asyncio
import json
import os
from openai import AsyncOpenAI
from fastmcp import Client

st.set_page_config(page_title="Agentic ODI Chat", page_icon="🚀", layout="wide")

st.title("Agentic ODI 🚀")
st.markdown("Chat with your ODI repository using a local LLM.")

# Configuration Sidebar
with st.sidebar:
    st.header("LLM Configuration")

    default_base_url = os.getenv("AGENTIC_ODI_BASE_URL", "http://localhost:8001/v1")
    default_api_key = os.getenv("AGENTIC_ODI_API_KEY", "local")
    default_model_name = os.getenv("AGENTIC_ODI_MODEL", "local-tools-model")
    default_mcp_url = os.getenv("AGENTIC_ODI_MCP_URL", "http://localhost:8000/mcp")

    base_url = st.text_input("Base URL", value=default_base_url)
    api_key = st.text_input("API Key", value=default_api_key, type="password")
    model_name = st.text_input("Model Name", value=default_model_name)
    mcp_url = st.text_input("MCP Server URL", value=default_mcp_url)

    # Surface resolved configuration for easier debugging
    st.caption(f"Using base URL: {base_url}")
    st.caption(f"Using model: {model_name}")

    # Basic configuration validation
    normalized_base_url = base_url.rstrip("/")
    if "/v1" not in normalized_base_url:
        st.warning(
            "The base URL does not appear to include a `/v1` prefix. "
            "If you are using an OpenAI-compatible server, double-check the URL."
        )

    if st.button("Clear Chat"):
        st.session_state.messages = []
        st.rerun()


def _classify_llm_error(exc: Exception) -> tuple[str, str]:
    """Classify an LLM error as connection-related or generic."""
    message = str(exc)
    lower = message.lower()
    connection_indicators = [
        "connection error",
        "connection aborted",
        "failed to establish a new connection",
        "timed out",
        "timeout",
        "connection refused",
    ]
    if any(indicator in lower for indicator in connection_indicators):
        return "connection_error", message
    return "error", message


async def _async_check_llm_health(
    health_base_url: str, health_api_key: str, health_model_name: str
) -> tuple[bool, str]:
    """Perform a lightweight health check against the LLM backend."""
    client = AsyncOpenAI(base_url=health_base_url, api_key=health_api_key)
    try:
        # Listing models is typically lightweight and supported by OpenAI-compatible servers.
        await client.models.list()
        return True, "LLM backend is reachable."
    except Exception as exc:  # noqa: BLE001
        status, detail = _classify_llm_error(exc)
        return False, f"{status}: {detail}"


def ensure_llm_health() -> None:
    """Update cached LLM health information when configuration changes."""
    config_key = f"{base_url}|{api_key}|{model_name}"

    if "llm_health" not in st.session_state:
        st.session_state.llm_health = {"healthy": None, "message": "Health not checked yet."}
        st.session_state.llm_health_config = None

    if st.session_state.llm_health_config == config_key:
        return

    try:
        healthy, message = asyncio.run(_async_check_llm_health(base_url, api_key, model_name))
    except Exception as exc:  # noqa: BLE001
        healthy, message = False, f"error_during_health_check: {exc}"

    st.session_state.llm_health = {"healthy": healthy, "message": message}
    st.session_state.llm_health_config = config_key


# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

# Ensure we have up-to-date LLM health information based on current config
ensure_llm_health()
llm_health = st.session_state.get("llm_health", {"healthy": None, "message": "Unknown"})

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if llm_health.get("healthy") is False:
    st.error(
        "Cannot reach the configured LLM backend. "
        f"Base URL: `{base_url}`. Details: {llm_health.get('message', '')}"
    )
    st.info(
        "Ensure your local tools-capable LLM server is running "
        "(for example, a `llama-cpp-python` server on `http://localhost:8001/v1` "
        "with model alias `local-tools-model`), then refresh this page."
    )


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
            openai_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters
                        if hasattr(tool, "parameters")
                        else tool.inputSchema,
                    },
                }
            )

        # 2. Add user message
        st.session_state.messages.append({"role": "user", "content": user_inp})

        # 3. Call LLM
        messages = [{"role": "system", "content": system_prompt}] + [
            {"role": m["role"], "content": m["content"]} for m in st.session_state.messages
        ]

        tools_arg = openai_tools if openai_tools else None
        tool_choice_arg = "auto" if openai_tools else None

        response = await llm_client.chat.completions.create(  # type: ignore[call-overload]
            model=model_name,
            messages=messages,
            tools=tools_arg,  # fastmcp tool schema is compatible at runtime
            tool_choice=tool_choice_arg,
        )

        message = response.choices[0].message

        # 4. Handle tool calls
        tool_calls = getattr(message, "tool_calls", None)
        if tool_calls:
            messages.append(message)  # Append assistant's tool call request
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": f"🛠️ Calling tools: {', '.join([tc.function.name for tc in tool_calls])}",
                }
            )

            for tool_call in tool_calls:
                func_name = tool_call.function.name
                try:
                    func_args = json.loads(tool_call.function.arguments or "{}")
                except json.JSONDecodeError:
                    func_args = {}

                # Execute against MCP server
                # In Streamlit, write status
                try:
                    tool_result = await mcp_client.call_tool(func_name, func_args)
                    result_str = str(tool_result)
                except Exception as e:
                    result_str = f"Error calling {func_name}: {str(e)}"

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": func_name,
                        "content": result_str,
                    }
                )

            # Second LLM call with tool results
            final_response = await llm_client.chat.completions.create(  # type: ignore[call-overload]
                model=model_name,
                messages=messages,
            )
            final_content = final_response.choices[0].message.content
        else:
            final_content = message.content

        st.session_state.messages.append({"role": "assistant", "content": final_content})
        return final_content


user_input = None

if llm_health.get("healthy") is not False:
    user_input = st.chat_input("Ask about or manage ODI data...")
else:
    st.stop()

if user_input:
    # Immediately render user message
    with st.chat_message("user"):
        st.markdown(user_input)

    system_prompt = """You are Agentic ODI, an AI assistant helping a user manage their Outcome-Driven Innovation (ODI) repository.
    You have tools to add and query Jobs-to-be-Done, Steps, and Outcomes.
    When a user asks you to do something, use your tools. If they ask a general question, use your tools to retrieve context."""

    error: Exception | None = None
    error_status: str | None = None
    with st.spinner("Thinking..."):
        # Run async function in sync Streamlit context
        try:
            asyncio.run(handle_user_input(user_input, system_prompt))
        except Exception as exc:  # noqa: BLE001
            error = exc
            status, _detail = _classify_llm_error(exc)
            error_status = status
            if status == "connection_error":
                # Mark health as bad so the next render surfaces guidance
                st.session_state.llm_health = {
                    "healthy": False,
                    "message": str(exc),
                }

    if error is not None:
        if error_status == "connection_error":
            st.error(
                "Cannot reach the LLM backend at the configured Base URL. "
                f"Base URL: `{base_url}`. Details: {error}"
            )
        else:
            st.error(f"Unexpected error while contacting LLM backend: {error}")
    else:
        st.rerun()
