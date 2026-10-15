"""The Living Studio — Minimum Viable Client GUI for Agentic ODI.

A spatial, conversational experience for Outcome-Driven Innovation:
- Canvas of Human Intent & Living Opportunity Map
- WYSIWYG Impact Simulation & Causal Lineage
- Dual Interaction: Conversational Agent + Direct Click Manipulation
- Ambient Local-First MCP and LLM Integration
- Progressive Loading & Shimmer Ghost Element Feedback (Streamlit Best Practice)
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import socket
from typing import Any
from urllib.parse import urlparse

import streamlit as st
from fastmcp import Client
from openai import AsyncOpenAI

# -----------------------------------------------------------------------------
# Streamlit Page Setup & Sleek Studio Glass & Ghost Elements Styling
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="The Living Studio | Agentic ODI",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    /* Dark glass studio theme accents */
    .stApp {
        background: radial-gradient(circle at 15% 15%, #131722 0%, #0b0d13 100%);
        color: #f1f5f9;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    .studio-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 12px 18px;
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        margin-bottom: 18px;
    }
    .studio-pill {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 9999px;
        font-size: 0.78rem;
        font-weight: 600;
        letter-spacing: 0.03em;
        text-transform: uppercase;
    }
    .pill-green {
        background: rgba(16, 185, 129, 0.15);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.3);
    }
    .pill-amber {
        background: rgba(245, 158, 11, 0.15);
        color: #fbbf24;
        border: 1px solid rgba(245, 158, 11, 0.3);
    }
    .pill-blue {
        background: rgba(99, 102, 241, 0.15);
        color: #818cf8;
        border: 1px solid rgba(99, 102, 241, 0.3);
    }
    .outcome-card {
        padding: 14px 18px;
        border-radius: 10px;
        background: rgba(255, 255, 255, 0.025);
        border: 1px solid rgba(255, 255, 255, 0.08);
        margin-bottom: 12px;
        transition: all 0.2s ease-in-out;
    }
    .outcome-card:hover {
        border-color: rgba(99, 102, 241, 0.4);
        background: rgba(255, 255, 255, 0.04);
    }
    .pulsing-card {
        border-left: 4px solid #f59e0b !important;
        box-shadow: 0 0 14px rgba(245, 158, 11, 0.18);
    }
    .evidence-box {
        background: rgba(15, 23, 42, 0.6);
        border-left: 3px solid #818cf8;
        padding: 10px 14px;
        border-radius: 6px;
        font-size: 0.86rem;
        margin-top: 8px;
    }

    /* Shimmer Ghost / Skeleton Loaders */
    @keyframes skeleton-shimmer {
        0% { background-position: -200% 0; }
        100% { background-position: 200% 0; }
    }
    .skeleton {
        background: linear-gradient(
            90deg,
            rgba(255, 255, 255, 0.03) 25%,
            rgba(255, 255, 255, 0.09) 50%,
            rgba(255, 255, 255, 0.03) 75%
        );
        background-size: 200% 100%;
        animation: skeleton-shimmer 1.6s infinite ease-in-out;
        border-radius: 6px;
    }
    .skeleton-card {
        padding: 16px 20px;
        border-radius: 10px;
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid rgba(255, 255, 255, 0.05);
        margin-bottom: 12px;
    }
    .skeleton-line {
        height: 14px;
        margin-bottom: 8px;
    }
    .skeleton-title {
        height: 22px;
        width: 65%;
        margin-bottom: 12px;
    }
    .skeleton-badge {
        height: 18px;
        width: 80px;
        border-radius: 9999px;
    }
    .skeleton-metric {
        height: 72px;
        border-radius: 8px;
        margin-bottom: 12px;
    }
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(4px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .fade-in {
        animation: fadeIn 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# Configuration & Environment Variables
# -----------------------------------------------------------------------------
default_base_url = os.getenv("AGENTIC_ODI_BASE_URL", "http://localhost:8001/v1")
default_api_key = os.getenv("AGENTIC_ODI_API_KEY", "local")
default_model_name = os.getenv("AGENTIC_ODI_MODEL", "local-tools-model")
default_mcp_url = os.getenv("AGENTIC_ODI_MCP_URL", "http://localhost:8000/mcp")

with st.sidebar:
    st.markdown("### 🎛️ **Living Studio Controls**")
    st.caption("Ambient intelligence and local harness connectivity.")

    base_url = st.text_input("LLM Base URL", value=default_base_url)
    api_key = st.text_input("LLM API Key", value=default_api_key, type="password")
    model_name = st.text_input("Model Alias", value=default_model_name)
    mcp_url = st.text_input("MCP Server URL", value=default_mcp_url)

    st.markdown("---")
    st.caption(f"**Target URL:** `{base_url}`")
    st.caption(f"**Target Model:** `{model_name}`")
    st.caption(f"**MCP Bridge:** `{mcp_url}`")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🧹 Clear Chat", use_container_width=True):
            st.session_state.messages = []
            st.rerun()
    with c2:
        if st.button("🔄 Sync Canvas", use_container_width=True):
            st.session_state.force_refresh = True
            st.rerun()

    st.markdown("---")
    st.markdown("#### ⚡ **MCP Sources (Connected)**")
    st.caption("🟢 **Local FastMCP Server** (`agentic-odi-mcp-server`)")
    st.caption("🟢 **Gong Audio Transcript Bridge** *(simulated)*")
    st.caption("🟢 **Slack Customer Friction Stream** *(simulated)*")
    st.caption("🟢 **Product Telemetry / PostHog** *(simulated)*")

    with st.expander("ℹ️ About the Living Studio"):
        st.markdown(
            """
            **The Living Studio** replaces backlogs and ticket accounting with a 
            **Canvas of Human Intent**.
            - **Point, Click, and Talk**: Direct spatial exploration paired with conversational AI.
            - **Causality, Not Features**: Trace every bet back to customer reality.
            - **WYSIWYG of Impact**: Simulate time saved before writing a line of code.
            """
        )


# -----------------------------------------------------------------------------
# Instant Connection Probing (Zero-Hang Non-Blocking Network Probe)
# -----------------------------------------------------------------------------
def is_endpoint_reachable(url: str, timeout: float = 0.3) -> bool:
    """Quick socket check to verify port is actively open without hanging on HTTP read timeouts."""
    try:
        parsed = urlparse(url)
        host = parsed.hostname or "localhost"
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _classify_llm_error(exc: Exception) -> tuple[str, str]:
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
    # First instant socket probe prevents 60-second hanging on dead localhost ports
    if not is_endpoint_reachable(health_base_url, timeout=0.3):
        return False, "LLM server offline (Local Studio Mode enabled)"

    client = AsyncOpenAI(base_url=health_base_url, api_key=health_api_key, timeout=1.2)
    try:
        # Wrap in tight timeout to guarantee immediate first-paint response
        await asyncio.wait_for(client.models.list(), timeout=1.2)
        return True, "LLM backend is reachable."
    except Exception as exc:  # noqa: BLE001
        status, detail = _classify_llm_error(exc)
        return False, f"{status}: {detail}"


def ensure_llm_health() -> None:
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


ensure_llm_health()
llm_health = st.session_state.get("llm_health", {"healthy": None, "message": "Unknown"})

# -----------------------------------------------------------------------------
# MCP Live Data Operations & Seed Sample Fallback
# -----------------------------------------------------------------------------
DEMO_JOBS = [
    {
        "id": "JOB-402",
        "name": "Sync Environment Secrets Across Microservices",
        "description": "Backend developers configuring microservice deployment pipelines across staging and production.",
    }
]

DEMO_STEPS = [
    {
        "id": "STP-1",
        "job_id": "JOB-402",
        "name": "1. Define required environment variables",
        "order": 1,
    },
    {
        "id": "STP-2",
        "job_id": "JOB-402",
        "name": "2. Locate credentials in Vault / 1Password",
        "order": 2,
    },
    {
        "id": "STP-3",
        "job_id": "JOB-402",
        "name": "3. Prepare secrets payload for cluster",
        "order": 3,
    },
    {
        "id": "STP-4",
        "job_id": "JOB-402",
        "name": "4. Confirm access permissions & scopes",
        "order": 4,
    },
    {
        "id": "STP-5",
        "job_id": "JOB-402",
        "name": "5. Execute manual copy-paste into CI/CD secrets",
        "order": 5,
    },
    {
        "id": "STP-6",
        "job_id": "JOB-402",
        "name": "6. Monitor pipeline build for config missing errors",
        "order": 6,
    },
    {
        "id": "STP-7",
        "job_id": "JOB-402",
        "name": "7. Modify mismatched keys upon failed deploy",
        "order": 7,
    },
    {"id": "STP-8", "job_id": "JOB-402", "name": "8. Conclude deployment confirmation", "order": 8},
]

DEMO_OUTCOMES = [
    {
        "id": "O-1",
        "job_id": "JOB-402",
        "statement": "Minimize the time taken to propagate secrets across environments",
        "importance": 9.2,
        "satisfaction": 3.1,
        "opportunity_score": 15.3,
        "evidence": "Customer Call #104: 'Lost 2 hours on dev due to manual copy-paste drift breaking staging.'",
        "telemetry": "45 min average manual friction across 400 deployment pipelines.",
    },
    {
        "id": "O-2",
        "job_id": "JOB-402",
        "statement": "Minimize the likelihood of exposing plain-text keys in build logs",
        "importance": 9.8,
        "satisfaction": 4.5,
        "opportunity_score": 15.1,
        "evidence": "Security Audit Q3: '3 accidental developer log leaks detected in git diffs.'",
        "telemetry": "Severity High: Compliance blocker for SOC2.",
    },
    {
        "id": "O-3",
        "job_id": "JOB-402",
        "statement": "Minimize the effort required to rotate expired tokens in running pods",
        "importance": 8.0,
        "satisfaction": 7.2,
        "opportunity_score": 8.8,
        "evidence": "DevOps Slack: 'Token rotation works well enough when using kubesecret operator.'",
        "telemetry": "Appropriately served area — low innovation priority.",
    },
]


async def fetch_mcp_data(mcp_endpoint: str) -> dict[str, Any]:
    """Fetch live data from the FastMCP server, non-blocking with fast timeout."""
    jobs: list[dict[str, Any]] = []
    outcomes: list[dict[str, Any]] = []
    steps: list[dict[str, Any]] = []

    # Quick socket probe prevents waiting when FastMCP server is not listening
    if not is_endpoint_reachable(mcp_endpoint, timeout=0.3):
        return {"jobs": DEMO_JOBS, "steps": DEMO_STEPS, "outcomes": DEMO_OUTCOMES}

    with contextlib.suppress(Exception):
        mcp_client = Client(mcp_endpoint)
        async with mcp_client:
            raw_jobs = await asyncio.wait_for(mcp_client.call_tool("get_jobs", {}), timeout=1.5)
            try:
                parsed_jobs = json.loads(str(raw_jobs))
                if isinstance(parsed_jobs, list):
                    jobs = parsed_jobs
            except Exception:  # noqa: BLE001
                jobs = []

            for job in jobs:
                job_id = job.get("id")
                if not job_id:
                    continue
                with contextlib.suppress(Exception):
                    raw_steps = await asyncio.wait_for(
                        mcp_client.call_tool("get_job_map", {"job_id": job_id}), timeout=1.0
                    )
                    parsed_steps = json.loads(str(raw_steps))
                    if isinstance(parsed_steps, list):
                        steps.extend(parsed_steps)

                with contextlib.suppress(Exception):
                    raw_outcomes = await asyncio.wait_for(
                        mcp_client.call_tool("get_outcomes", {"job_id": job_id}), timeout=1.0
                    )
                    parsed_outcomes = json.loads(str(raw_outcomes))
                    if isinstance(parsed_outcomes, list):
                        outcomes.extend(parsed_outcomes)

    # If repository is empty, populate with seed prototype data
    if not jobs:
        jobs = DEMO_JOBS
        steps = DEMO_STEPS
        outcomes = DEMO_OUTCOMES

    return {"jobs": jobs, "steps": steps, "outcomes": outcomes}


# Progressive Data Hydration with Visual User Feedback
is_first_load = "mcp_data" not in st.session_state
if is_first_load or st.session_state.get("force_refresh"):
    # Progressive feedback banner
    with st.status(
        "⚡ Syncing with Living Studio Canvas & FastMCP...", expanded=False
    ) as load_status:
        try:
            st.session_state.mcp_data = asyncio.run(fetch_mcp_data(mcp_url))
            load_status.update(
                label="✨ Living Studio Canvas ready", state="complete", expanded=False
            )
        except Exception:  # noqa: BLE001
            st.session_state.mcp_data = {
                "jobs": DEMO_JOBS,
                "steps": DEMO_STEPS,
                "outcomes": DEMO_OUTCOMES,
            }
            load_status.update(
                label="🟢 Local Studio Prototype Loaded", state="complete", expanded=False
            )
    st.session_state.force_refresh = False

current_jobs = st.session_state.mcp_data.get("jobs", DEMO_JOBS)
current_steps = st.session_state.mcp_data.get("steps", DEMO_STEPS)
current_outcomes = st.session_state.mcp_data.get("outcomes", DEMO_OUTCOMES)


# -----------------------------------------------------------------------------
# Ghost / Skeleton Visual Feedback Helper Functions
# -----------------------------------------------------------------------------
def render_ghost_metrics() -> None:
    """Render shimmering skeleton metric cards."""
    st.markdown(
        """
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 16px;">
            <div class="skeleton skeleton-metric"></div>
            <div class="skeleton skeleton-metric"></div>
            <div class="skeleton skeleton-metric"></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_ghost_opportunity_cards(count: int = 3) -> None:
    """Render shimmering skeleton opportunity cards."""
    for _ in range(count):
        st.markdown(
            """
            <div class="skeleton-card">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div class="skeleton skeleton-line" style="width: 60px; height: 16px;"></div>
                    <div class="skeleton skeleton-badge"></div>
                </div>
                <div class="skeleton skeleton-title" style="margin-top: 10px;"></div>
                <div class="skeleton skeleton-line" style="width: 45%;"></div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_ghost_job_steps(count: int = 4) -> None:
    """Render shimmering skeleton job steps."""
    for _ in range(count):
        st.markdown(
            """
            <div class="skeleton skeleton-line" style="height: 38px; border-radius: 8px; margin-bottom: 8px;"></div>
            """,
            unsafe_allow_html=True,
        )


# -----------------------------------------------------------------------------
# Studio Top Bar (The Pulse of Human Intent)
# -----------------------------------------------------------------------------
col_header_left, col_header_right = st.columns([0.7, 0.3])

with col_header_left:
    st.markdown(
        """
        <div class="studio-header fade-in">
            <div>
                <span style="font-size: 1.5rem; font-weight: 700; letter-spacing: -0.02em;">
                    The Living Studio <span style="opacity: 0.5; font-size: 1rem;">| Outcome-Driven Innovation</span>
                </span>
                <div style="font-size: 0.85rem; color: #94a3b8; margin-top: 2px;">
                    A Canvas of Human Intent. Zero file trees. Real-time causality.
                </div>
            </div>
            <div>
                <span class="studio-pill pill-blue">ODI Framework v1.0</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col_header_right:
    llm_status_badge = (
        '<span class="studio-pill pill-green">🟢 LLM Active</span>'
        if llm_health.get("healthy")
        else '<span class="studio-pill pill-amber">🟡 Local Studio Mode</span>'
    )
    mcp_badge = (
        '<span class="studio-pill pill-green" style="margin-left: 6px;">🟢 FastMCP Connected</span>'
        if is_endpoint_reachable(mcp_url)
        else '<span class="studio-pill pill-blue" style="margin-left: 6px;">⚡ Seed Prototype Ready</span>'
    )
    st.markdown(
        f"""
        <div style="text-align: right; padding-top: 10px;" class="fade-in">
            {llm_status_badge}
            {mcp_badge}
        </div>
        """,
        unsafe_allow_html=True,
    )

# -----------------------------------------------------------------------------
# Conversational Helper / Tool Calling Execution
# -----------------------------------------------------------------------------
SYSTEM_PROMPT = """You are Steve Jobs and an elite Outcome-Driven Innovation (ODI) strategist assisting a Product Manager in The Living Studio.
Your mission is to eliminate backlog paper-pushing and help the PM think exclusively in human intent, customer friction, and measurable outcomes.
Key principles:
1. Always start with the Job-to-be-Done (JTBD): "What is the core functional human job?"
2. Uncover Desired Outcomes using the strict ODI format: [Direction] + [Unit of Measure] + [Object of Control] + [Contextual Clarifier]. (e.g. "Minimize the time it takes to propagate secrets across environments").
3. Opportunity Score = Importance + max(Importance - Satisfaction, 0). Scores > 10 represent breakthrough underserved market opportunities.
4. When asked to add or query Jobs, Steps, or Outcomes, ALWAYS invoke the corresponding tools.
5. Embody clarity, focus, and causality. Strip away corporate jargon."""


async def handle_user_input(user_inp: str, prompt_override: str | None = None) -> str:
    active_prompt = prompt_override or SYSTEM_PROMPT
    st.session_state.messages.append({"role": "user", "content": user_inp})

    # If LLM backend is not reachable, provide intelligent grounded fallback immediately
    if not llm_health.get("healthy"):
        lower_inp = user_inp.lower()
        if "guideline" in lower_inp or "framework" in lower_inp or "stage" in lower_inp:
            reply = (
                "### 📖 Outcome-Driven Innovation (ODI) Process Guidelines\n\n"
                "1. **Stage 1: Define Intent (Job-to-be-Done)** — Identify the core functional human goal.\n"
                "2. **Stage 2: Capture Desired Outcomes** — Success metrics: `[Direction] + [Unit] + [Object] + [Context]`.\n"
                "3. **Stage 3: Opportunity Scoring** — `Importance + max(Importance - Satisfaction, 0)`. Focus on scores > 10.\n"
                "4. **Stage 4: Universal Job Map** — Map the 8 stages: Define ➔ Locate ➔ Prepare ➔ Confirm ➔ Execute ➔ Monitor ➔ Modify ➔ Conclude.\n\n"
                "*(Connected in Local Studio Mode. Start your local LLM backend at `http://localhost:8001/v1` for full autonomous completions)*"
            )
        elif "simulate" in lower_inp or "bet" in lower_inp or "impact" in lower_inp:
            reply = (
                "### ⚡ WYSIWYG Impact Simulation Result\n\n"
                "- **Target Outcome**: O-1 (*Minimize time taken to propagate secrets*)\n"
                "- **Proposed Bet**: Automated Secret Sync Daemon\n"
                "- **Before**: 45 minutes of manual copy-paste across 400 developer pipelines.\n"
                "- **After**: Under 30 seconds ambient zero-touch sync.\n"
                "- **Time-to-Value Shift**: **-90% friction reduction**.\n"
                "- **Human Impact**: 3,000 hours of developer agony eliminated every month. Build it."
            )
        elif "evidence" in lower_inp or "call" in lower_inp or "quote" in lower_inp:
            reply = (
                "### 🔍 Causal Lineage: Real-Time Evidence\n\n"
                "- **Signal Source**: Gong Call #104 (Enterprise Team Alpha)\n"
                "- **Customer Voice**: *'We lost two hours on deploy day because someone missed a database config key.'*\n"
                "- **Telemetry**: 400 microservices impacted weekly; 14% failed build rate attributed to config drift."
            )
        else:
            reply = (
                f'I received your intent: **"{user_inp}"**.\n\n'
                "In The Living Studio, every idea is evaluated against human outcomes rather than story points. "
                "Notice how our highest opportunity outcome (`O-1: Minimize propagation time`) has an **Opportunity Score of 15.3**, "
                "signaling severe market underservice. Tap **'Simulate Impact'** on the canvas or type `Simulate Auto-Sync Bet` to test causality."
            )
        st.session_state.messages.append({"role": "assistant", "content": reply})
        return reply

    # Live OpenAI-compatible tool loop
    llm_client = AsyncOpenAI(base_url=base_url, api_key=api_key, timeout=15.0)
    mcp_client = Client(mcp_url)

    async with mcp_client:
        mcp_tools = await mcp_client.list_tools()
        openai_tools = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_schema,
                },
            }
            for tool in mcp_tools
        ]

        messages = [{"role": "system", "content": active_prompt}] + [
            {"role": m["role"], "content": m["content"]} for m in st.session_state.messages
        ]

        response = await llm_client.chat.completions.create(  # type: ignore[call-overload]
            model=model_name,
            messages=messages,
            tools=openai_tools if openai_tools else None,
            tool_choice="auto" if openai_tools else None,
        )

        message = response.choices[0].message
        tool_calls = getattr(message, "tool_calls", None)

        if tool_calls:
            messages.append(message)
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": f"🛠️ **Executing Causal Tools**: {', '.join([tc.function.name for tc in tool_calls])}",
                }
            )

            for tool_call in tool_calls:
                func_name = tool_call.function.name
                try:
                    func_args = json.loads(tool_call.function.arguments or "{}")
                except json.JSONDecodeError:
                    func_args = {}

                try:
                    tool_result = await mcp_client.call_tool(func_name, func_args)
                    result_str = str(tool_result)
                except Exception as e:  # noqa: BLE001
                    result_str = f"Error calling {func_name}: {e}"

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": func_name,
                        "content": result_str,
                    }
                )

            # Trigger fresh data sync after tool writes
            st.session_state.force_refresh = True

            final_response = await llm_client.chat.completions.create(  # type: ignore[call-overload]
                model=model_name,
                messages=messages,
            )
            final_content = final_response.choices[0].message.content or ""
        else:
            final_content = message.content or ""

        st.session_state.messages.append({"role": "assistant", "content": final_content})
        return final_content


# -----------------------------------------------------------------------------
# Main Living Studio Interface: Spatial Canvas (Left) + Agentic Copilot (Right)
# -----------------------------------------------------------------------------
canvas_col, chat_col = st.columns([0.58, 0.42], gap="medium")

# =============================================================================
# LEFT HEMISPHERE: The Living Spatial Canvas
# =============================================================================
with canvas_col:
    canvas_tabs = st.tabs(
        [
            "🌟 Opportunity Landscape",
            "🗺️ Universal Job Map",
            "⚡ WYSIWYG Impact",
            "📡 Customer Evidence",
            "➕ Direct Capture",
        ]
    )

    # -------------------------------------------------------------------------
    # TAB 1: Opportunity Landscape
    # -------------------------------------------------------------------------
    with canvas_tabs[0]:
        st.markdown("#### **The Landscape of Human Need**")
        st.caption("Outcomes with Opportunity Scores > 10 pulse as urgent innovation targets.")

        # Metric summary
        underserved_count = sum(
            1 for o in current_outcomes if (o.get("opportunity_score") or 0) > 10.0
        )
        m_c1, m_c2, m_c3 = st.columns(3)
        with m_c1:
            st.metric("Active Jobs", len(current_jobs))
        with m_c2:
            st.metric("Underserved (>10)", underserved_count, delta="High Potential")
        with m_c3:
            st.metric("Total Outcomes", len(current_outcomes))

        st.markdown("---")

        for outcome in current_outcomes:
            opp = outcome.get("opportunity_score")
            imp = outcome.get("importance")
            sat = outcome.get("satisfaction")
            statement = outcome.get("statement", "Untitled Outcome")
            outcome_id = outcome.get("id", "O")
            is_underserved = opp is not None and opp > 10.0

            card_class = (
                "outcome-card pulsing-card fade-in" if is_underserved else "outcome-card fade-in"
            )
            pill_badge = (
                f'<span class="studio-pill pill-amber">🔥 Underserved (Opp: {opp:.1f})</span>'
                if is_underserved
                else f'<span class="studio-pill pill-green">✓ Served (Opp: {opp:.1f} if opp else "N/A")</span>'
            )

            st.markdown(
                f"""
                <div class="{card_class}">
                    <div style="display: flex; justify-content: space-between; align-items: baseline;">
                        <span style="font-weight: 700; color: #818cf8;">{outcome_id}</span>
                        {pill_badge}
                    </div>
                    <div style="font-size: 1rem; font-weight: 500; margin: 8px 0;">
                        "{statement}"
                    </div>
                    <div style="font-size: 0.82rem; color: #94a3b8;">
                        Importance: <b>{imp if imp is not None else "—"}/10</b> &nbsp;|&nbsp; 
                        Current Satisfaction: <b>{sat if sat is not None else "—"}/10</b> &nbsp;|&nbsp; 
                        Formula: <i>Imp + max(Imp - Sat, 0)</i>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Direct action buttons beneath outcome card
            act_col1, act_col2, act_col3 = st.columns([0.33, 0.33, 0.34])
            with act_col1:
                if st.button(
                    f"🔍 Inspect Trace ({outcome_id})",
                    key=f"trace_{outcome_id}",
                    use_container_width=True,
                ):
                    evidence_text = outcome.get("evidence", "No transcript linked.")
                    st.info(f"**Customer Evidence Lineage:**\n\n{evidence_text}")
            with act_col2:
                if st.button(
                    f"⚡ Simulate Bet ({outcome_id})",
                    key=f"sim_{outcome_id}",
                    use_container_width=True,
                ):
                    st.session_state.pending_sim_outcome = outcome_id
                    st.success(f"Outcome {outcome_id} loaded into WYSIWYG Impact Simulator.")
            with act_col3:
                if st.button(
                    f"💬 Ask Agent ({outcome_id})",
                    key=f"ask_{outcome_id}",
                    use_container_width=True,
                ):
                    asyncio.run(
                        handle_user_input(
                            f"How should we solve outcome {outcome_id}: '{statement}'?"
                        )
                    )
                    st.rerun()

    # -------------------------------------------------------------------------
    # TAB 2: Universal Job Map
    # -------------------------------------------------------------------------
    with canvas_tabs[1]:
        st.markdown("#### **Universal Job Map (8 Process Phases)**")
        st.caption(
            "Ulwick Universal Job Steps: Define ➔ Locate ➔ Prepare ➔ Confirm ➔ Execute ➔ Monitor ➔ Modify ➔ Conclude"
        )

        if current_steps:
            for step in current_steps:
                st.markdown(
                    f"""
                    <div class="fade-in" style="padding: 10px 14px; background: rgba(255, 255, 255, 0.03); border-radius: 8px; margin-bottom: 8px; border-left: 3px solid #6366f1;">
                        <b>Step {step.get("order", "")}</b>: {step.get("name", "")}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.info(
                "No job steps registered yet. Ask the AI assistant to decompose the active job!"
            )

        with st.expander("➕ Add Step to Job Map"):
            with st.form("add_step_form"):
                step_name = st.text_input("Step Description (e.g., '3. Prepare secrets payload')")
                step_order = st.number_input(
                    "Step Chronological Order",
                    min_value=1,
                    max_value=20,
                    value=len(current_steps) + 1,
                )
                submit_step = st.form_submit_button("Add Step to Map")
                if submit_step and step_name:
                    active_job_id = current_jobs[0]["id"] if current_jobs else "JOB-402"
                    try:

                        async def _add_step():
                            m_client = Client(mcp_url)
                            async with m_client:
                                return await m_client.call_tool(
                                    "add_step",
                                    {
                                        "job_id": active_job_id,
                                        "name": step_name,
                                        "order": int(step_order),
                                    },
                                )

                        asyncio.run(_add_step())
                        st.session_state.force_refresh = True
                        st.success("Step added to Job Map!")
                        st.rerun()
                    except Exception as e:  # noqa: BLE001
                        st.error(f"Error adding step: {e}")

    # -------------------------------------------------------------------------
    # TAB 3: WYSIWYG Impact Simulation
    # -------------------------------------------------------------------------
    with canvas_tabs[2]:
        st.markdown("#### **WYSIWYG of Human Impact**")
        st.caption(
            "What You See Is What They Experience. Simulate the collapse of human friction before writing code."
        )

        selected_sim_outcome = st.selectbox(
            "Target Desired Outcome",
            options=[f"{o.get('id')}: {o.get('statement')}" for o in current_outcomes],
            index=0 if current_outcomes else 0,
        )

        bet_proposal = st.text_input(
            "Feature Bet / Concept",
            value="Automated Secret Sync Daemon (Zero-Touch Ambient Sync)",
        )

        st.markdown("##### **Reality Simulation Preview**")
        sim_c1, sim_c2 = st.columns(2)
        with sim_c1:
            st.markdown(
                """
                <div class="fade-in" style="background: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.2); padding: 14px; border-radius: 8px;">
                    <span class="studio-pill" style="background: rgba(239,68,68,0.2); color: #f87171;">BEFORE (Current Reality)</span>
                    <ul style="margin-top: 8px; font-size: 0.88rem; color: #cbd5e1;">
                        <li><b>45 minutes</b> manual copy-paste across staging and production.</li>
                        <li><b>14% deploy failure</b> caused by key configuration drift.</li>
                        <li>400 engineering teams suffer daily friction.</li>
                    </ul>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with sim_c2:
            st.markdown(
                """
                <div class="fade-in" style="background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.2); padding: 14px; border-radius: 8px;">
                    <span class="studio-pill pill-green">AFTER (Simulated Value)</span>
                    <ul style="margin-top: 8px; font-size: 0.88rem; color: #cbd5e1;">
                        <li><b>&lt; 30 seconds</b> automated background propagation.</li>
                        <li><b>Zero human steps</b>. Ambient credential synchronization.</li>
                        <li><b>3,000 hours</b> of team agony eliminated per month.</li>
                    </ul>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("<br>", unsafe_allow_html=True)
        met_c1, met_c2, met_c3 = st.columns(3)
        with met_c1:
            st.metric("Time-to-Value Shift", "-90%", delta="Friction Eliminated")
        with met_c2:
            st.metric("Satisfaction Projection", "8.9 / 10", delta="+5.8 pts")
        with met_c3:
            st.metric("Implementation Risk", "Low", delta="Non-breaking")

        if st.button("🚀 Declare Intent -> Approve Bet & Draft PDR", use_container_width=True):
            asyncio.run(
                handle_user_input(
                    f"Draft a Product Decision Record (PDR) for approved bet: '{bet_proposal}' target outcome '{selected_sim_outcome}'."
                )
            )
            st.success("Product Decision Record drafted by the agent!")
            st.rerun()

    # -------------------------------------------------------------------------
    # TAB 4: Customer Evidence Pulse (MCP Stubs)
    # -------------------------------------------------------------------------
    with canvas_tabs[3]:
        st.markdown("#### **Customer Evidence Stream**")
        st.caption("Live signals streaming from Gong, Slack, and product telemetry via MCP.")

        st.markdown(
            """
            <div class="evidence-box fade-in">
                <span style="font-weight: 700; color: #fbbf24;">🎙️ Gong Call #104 (Tech Lead - FinTech Corp)</span>
                <p style="margin-top: 4px; font-style: italic;">
                    "We had a junior engineer push code that failed staging because the Stripe secret wasn't copied over. 
                    It took 3 senior engineers 2 hours to figure out why the cluster wouldn't spin up. 
                    There has to be a better way than copy-pasting strings."
                </p>
                <span style="font-size: 0.75rem; color: #94a3b8;">Linked to: <b>JOB-402 / Outcome O-1</b> • Severity: High</span>
            </div>
            <div class="evidence-box fade-in" style="border-left-color: #34d399; margin-top: 10px;">
                <span style="font-weight: 700; color: #34d399;">💬 Customer Slack Friction Alert (#incident-deployments)</span>
                <p style="margin-top: 4px; font-style: italic;">
                    "Third time this week staging broke after secret rotation. We need automated synchronization."
                </p>
                <span style="font-size: 0.75rem; color: #94a3b8;">Linked to: <b>JOB-402 / Outcome O-2</b> • Severity: Critical</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.caption(
            "💡 *In Phase 2, external MCP connectors populate this stream continuously into the SQLite Intent Store.*"
        )

    # -------------------------------------------------------------------------
    # TAB 5: Direct Capture (Form Alternative to Chat)
    # -------------------------------------------------------------------------
    with canvas_tabs[4]:
        st.markdown("#### **Direct Capture: Jobs & Outcomes**")
        st.caption(
            "Prefer direct entry over conversational typing? Add artifacts directly to the MCP repository."
        )

        with st.form("direct_add_outcome_form"):
            target_job_id = st.selectbox(
                "Select Job",
                options=[j["id"] for j in current_jobs],
                format_func=lambda j_id: next(
                    (f"{j['id']}: {j['name']}" for j in current_jobs if j["id"] == j_id), j_id
                ),
            )
            new_statement = st.text_input(
                "Desired Outcome Statement",
                placeholder="Minimize the time it takes to...",
                help="Format: [Direction] + [Unit of Measure] + [Object of Control] + [Contextual Clarifier]",
            )
            col_imp, col_sat = st.columns(2)
            with col_imp:
                new_importance = st.slider("Importance Score (1-10)", 1.0, 10.0, 8.5, 0.1)
            with col_sat:
                new_satisfaction = st.slider("Current Satisfaction (1-10)", 1.0, 10.0, 3.5, 0.1)

            # Live preview of Opportunity Score calculation
            calc_opp = new_importance + max(new_importance - new_satisfaction, 0.0)
            st.info(
                f"📊 **Calculated Opportunity Score**: `{calc_opp:.2f}` ({'🔥 Underserved' if calc_opp > 10 else 'Appropriately Served'})"
            )

            submit_outcome = st.form_submit_button("Record Desired Outcome")
            if submit_outcome and new_statement:
                try:

                    async def _add_outcome():
                        m_client = Client(mcp_url)
                        async with m_client:
                            return await m_client.call_tool(
                                "add_outcome",
                                {
                                    "job_id": target_job_id,
                                    "statement": new_statement,
                                    "importance": new_importance,
                                    "satisfaction": new_satisfaction,
                                },
                            )

                    asyncio.run(_add_outcome())
                    st.session_state.force_refresh = True
                    st.success("Outcome captured successfully!")
                    st.rerun()
                except Exception as e:  # noqa: BLE001
                    st.error(f"Error capturing outcome: {e}")

# =============================================================================
# RIGHT HEMISPHERE: The Agentic Conversational Copilot
# =============================================================================
with chat_col:
    st.markdown("#### 💬 **Agentic Studio Copilot**")
    st.caption(
        "Direct thought interaction. Speak your intent; the agent navigates the ODI methodology."
    )

    # Quick prompt pills for instantaneous exploration
    st.markdown("**Suggested Intents:**")
    qp_c1, qp_c2, qp_c3 = st.columns(3)
    with qp_c1:
        if st.button("🎯 Define Job", use_container_width=True):
            asyncio.run(
                handle_user_input("Help me define a new Job-to-be-Done for developer platforms.")
            )
            st.rerun()
    with qp_c2:
        if st.button("⚡ Simulate Bet", use_container_width=True):
            asyncio.run(
                handle_user_input("Simulate the impact of an Auto-Sync Agent on outcome O-1.")
            )
            st.rerun()
    with qp_c3:
        if st.button("📖 Guidelines", use_container_width=True):
            asyncio.run(handle_user_input("Give me the ODI Stage-by-Stage guidelines."))
            st.rerun()

    # Chat history container
    chat_container = st.container(height=480)
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": (
                    "Welcome to **The Living Studio**. We have eliminated backlogs and Jira spreadsheets.\n\n"
                    "You are looking at a living map of human progress. Tell me what your customers are struggling with, "
                    "or click on any outcome on the canvas to inspect its causality."
                ),
            }
        ]

    with chat_container:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # Conversational chat input
    user_input = st.chat_input("State your product intent or question...")
    if user_input:
        with chat_container:
            with st.chat_message("user"):
                st.markdown(user_input)

        with st.spinner("Synthesizing human intent & outcomes..."):
            try:
                asyncio.run(handle_user_input(user_input))
            except Exception as exc:  # noqa: BLE001
                st.error(f"Error during assistant completion: {exc}")
        st.rerun()
