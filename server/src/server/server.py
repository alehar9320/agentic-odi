import uuid
from enum import StrEnum

from fastmcp import FastMCP
from pydantic import BaseModel, Field, computed_field

mcp = FastMCP("Agentic ODI Server")


# --- Enums and Computation ---


class Direction(StrEnum):
    MINIMIZE = "minimize"
    MAXIMIZE = "maximize"


class BusinessImpactCategory(StrEnum):
    REVENUE_GROWTH = "revenue_growth"
    COST_REDUCTION = "cost_reduction"
    RETENTION = "retention"
    RISK_MITIGATION = "risk_mitigation"
    OPERATIONAL_EFFICIENCY = "operational_efficiency"
    COMPLIANCE = "compliance"
    BRAND_REPUTATION = "brand_reputation"
    OTHER = "other"


def compute_opportunity_score(importance: float, satisfaction: float) -> float:
    """ODI Opportunity Score = importance + max(importance - satisfaction, 0)."""
    return float(importance + max(importance - satisfaction, 0.0))


# --- ODI System Prompt ---
# This prompt initializes any client AI agent connecting to this server
# with the ODI methodology and instructs it how to guide end-users.


@mcp.prompt()
def odi_assistant_prompt() -> str:
    """System prompt for the client AI agent: establishes ODI methodology, persona, and user-guidance rules."""
    return (
        "You are an expert Outcome-Driven Innovation (ODI) assistant powered by the Jobs-to-be-Done (JTBD) theory. "
        "Your primary role is to actively guide users through the ODI process — do not just react to what they ask; proactively lead them forward.\n\n"
        "## Your guiding principles:\n"
        "1. **Start with Intent**: Before anything else, understand WHAT the user is trying to accomplish. "
        "If no Job-to-be-Done has been defined yet, always begin by asking the user to articulate their core job (e.g., 'What is the main task or goal your customer is trying to achieve?'). "
        "Use `add_job` to capture it once identified.\n"
        "2. **Focus on Outcomes before Solutions**: Once a Job is defined, guide the user to articulate *desired outcomes* — measurable statements of success — "
        "before jumping to features, steps, or implementation. Use `add_outcome` to capture them.\n"
        "3. **Build the Job Map next**: Only after outcomes are captured, help the user decompose the job into chronological Steps using `add_step` and `get_job_map`.\n"
        "4. **Prioritize by Opportunity Score**: Encourage the user to rate importance and satisfaction for each outcome. "
        "Outcomes with a high Opportunity Score (importance + max(importance - satisfaction, 0)) signal the highest innovation potential.\n"
        "5. **Tool Guidance**: Call `get_odi_framework_guidelines` whenever you need a structured reminder of which tool to use at each stage.\n\n"
        "Never skip ahead. Always confirm the user's intent before moving to the next ODI stage."
    )


# --- Pydantic Models for ODI Artifacts ---


class Job(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., description="The name of the Job-to-be-Done")
    description: str | None = Field(None, description="Detailed description of the Job")


class Step(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    job_id: str = Field(..., description="The ID of the Job this step belongs to")
    name: str = Field(..., description="The name of the job step")
    order: int = Field(..., description="The chronological order of this step in the job map")


class Outcome(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    job_id: str = Field(..., description="The ID of the Job this outcome relates to")
    step_id: str | None = Field(None, description="The ID of the specific Step, if applicable")
    statement: str = Field(
        ..., description="The desired outcome statement (e.g., 'Minimize the time it takes to...')"
    )
    importance: float | None = Field(None, ge=1.0, le=10.0, description="Importance score (1-10)")
    satisfaction: float | None = Field(
        None, ge=1.0, le=10.0, description="Current satisfaction score (1-10)"
    )
    opportunity_score: float | None = Field(
        None, description="Opportunity score (Importance + max(Importance - Satisfaction, 0))"
    )


class ValueMetric(BaseModel):
    """A single measurable dimension of value."""

    name: str
    direction: Direction
    unit_of_measure: str
    importance: float = Field(ge=1.0, le=10.0)
    satisfaction: float = Field(ge=1.0, le=10.0)

    @computed_field
    @property
    def opportunity_score(self) -> float:
        return compute_opportunity_score(self.importance, self.satisfaction)


class CustomerValue(BaseModel):
    direction: Direction
    unit_of_measure: str
    object_of_control: str
    contextual_clarifier: str | None = None
    statement: str
    importance: float = Field(ge=1.0, le=10.0)
    satisfaction: float = Field(ge=1.0, le=10.0)
    value_metrics: list[ValueMetric] = Field(default_factory=list)

    @computed_field
    @property
    def opportunity_score(self) -> float:
        return compute_opportunity_score(self.importance, self.satisfaction)


class BusinessValue(BaseModel):
    category: BusinessImpactCategory
    statement: str
    detail: str | None = None
    estimated_annual_value: float | None = Field(default=None, ge=0.0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class CustomerOutcome(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    job_id: str = Field(..., description="The ID of the Job this outcome relates to")
    step_id: str | None = Field(
        default=None, description="The ID of the specific Step, if applicable"
    )
    customer_value: CustomerValue
    business_value: BusinessValue


# --- In-Memory Storage ---
# For sandbox testing. In production, connect to a rigorous database.
jobs_db: dict[str, Job] = {}
steps_db: dict[str, Step] = {}
outcomes_db: dict[str, Outcome] = {}
customer_outcomes_db: dict[str, CustomerOutcome] = {}

# --- MCP Tools ---


@mcp.tool
def add_job(name: str, description: str | None = None) -> str:
    """Add a new Job-to-be-Done to the ODI repository."""
    job = Job(name=name, description=description)
    jobs_db[job.id] = job
    return f"Job created successfully: {job.model_dump_json()}"


@mcp.tool
def get_jobs() -> str:
    """Retrieve all stored Jobs."""
    return f"[{', '.join(job.model_dump_json() for job in jobs_db.values())}]"


@mcp.tool
def get_job(job_id: str) -> str:
    """Retrieve a specific Job by its ID."""
    if job_id not in jobs_db:
        return f"Error: Job with ID {job_id} not found."
    return jobs_db[job_id].model_dump_json()


@mcp.tool
def add_step(job_id: str, name: str, order: int) -> str:
    """Add a new Step to a Job's Job Map."""
    if job_id not in jobs_db:
        return f"Error: Job with ID {job_id} not found."
    step = Step(job_id=job_id, name=name, order=order)
    steps_db[step.id] = step
    return f"Step created successfully: {step.model_dump_json()}"


@mcp.tool
def get_job_map(job_id: str) -> str:
    """Retrieve the Job Map (all Steps, ordered) for a specific Job."""
    if job_id not in jobs_db:
        return f"Error: Job with ID {job_id} not found."
    job_steps = [step for step in steps_db.values() if step.job_id == job_id]
    job_steps.sort(key=lambda x: x.order)
    return f"[{', '.join(step.model_dump_json() for step in job_steps)}]"


@mcp.tool
def add_outcome(
    job_id: str,
    statement: str,
    step_id: str | None = None,
    importance: float | None = None,
    satisfaction: float | None = None,
) -> str:
    """Add a Desired Outcome to a Job, optionally calculating the Opportunity Score."""
    if job_id not in jobs_db:
        return f"Error: Job with ID {job_id} not found."

    op_score = None
    if importance is not None and satisfaction is not None:
        op_score = importance + max(importance - satisfaction, 0)

    outcome = Outcome(
        job_id=job_id,
        step_id=step_id,
        statement=statement,
        importance=importance,
        satisfaction=satisfaction,
        opportunity_score=op_score,
    )
    outcomes_db[outcome.id] = outcome
    return f"Outcome created successfully: {outcome.model_dump_json()}"


@mcp.tool
def add_customer_outcome(
    job_id: str,
    customer_value: CustomerValue,
    business_value: BusinessValue,
    step_id: str | None = None,
) -> str:
    """Add a new Customer Outcome capturing both customer and business value."""
    if job_id not in jobs_db:
        return f"Error: Job with ID {job_id} not found."
    outcome = CustomerOutcome(
        job_id=job_id,
        step_id=step_id,
        customer_value=customer_value,
        business_value=business_value,
    )
    customer_outcomes_db[outcome.id] = outcome
    return f"Customer outcome created successfully: {outcome.model_dump_json()}"


@mcp.tool
def get_customer_outcome(outcome_id: str) -> str:
    """Retrieve a specific Customer Outcome by ID."""
    if outcome_id not in customer_outcomes_db:
        return f"Error: Customer outcome with ID {outcome_id} not found."
    return customer_outcomes_db[outcome_id].model_dump_json()


@mcp.tool
def list_customer_outcomes(job_id: str | None = None) -> str:
    """List all Customer Outcomes, optionally filtered by job."""
    rows = [o for o in customer_outcomes_db.values() if job_id is None or o.job_id == job_id]
    return f"[{', '.join(o.model_dump_json() for o in rows)}]"


@mcp.tool
def update_customer_outcome(
    outcome_id: str,
    customer_value: CustomerValue | None = None,
    business_value: BusinessValue | None = None,
    step_id: str | None = None,
    direction: Direction | None = None,
    unit_of_measure: str | None = None,
    object_of_control: str | None = None,
    contextual_clarifier: str | None = None,
    statement: str | None = None,
    importance: float | None = None,
    satisfaction: float | None = None,
    category: BusinessImpactCategory | None = None,
    business_statement: str | None = None,
    detail: str | None = None,
    estimated_annual_value: float | None = None,
    confidence: float | None = None,
) -> str:
    """Update an existing Customer Outcome (merges partial fields)."""
    if outcome_id not in customer_outcomes_db:
        return f"Error: Customer outcome with ID {outcome_id} not found."
    outcome = customer_outcomes_db[outcome_id]
    if customer_value is not None:
        outcome.customer_value = customer_value
    else:
        cv_data = outcome.customer_value.model_dump()
        if direction is not None:
            cv_data["direction"] = direction
        if unit_of_measure is not None:
            cv_data["unit_of_measure"] = unit_of_measure
        if object_of_control is not None:
            cv_data["object_of_control"] = object_of_control
        if contextual_clarifier is not None or "contextual_clarifier" in cv_data:
            cv_data["contextual_clarifier"] = contextual_clarifier
        if statement is not None:
            cv_data["statement"] = statement
        if importance is not None:
            cv_data["importance"] = importance
        if satisfaction is not None:
            cv_data["satisfaction"] = satisfaction
        outcome.customer_value = CustomerValue.model_validate(cv_data)
    if business_value is not None:
        outcome.business_value = business_value
    else:
        bv_data = outcome.business_value.model_dump()
        if category is not None:
            bv_data["category"] = category
        if business_statement is not None:
            bv_data["statement"] = business_statement
        if detail is not None or "detail" in bv_data:
            bv_data["detail"] = detail
        if estimated_annual_value is not None or "estimated_annual_value" in bv_data:
            bv_data["estimated_annual_value"] = estimated_annual_value
        if confidence is not None or "confidence" in bv_data:
            bv_data["confidence"] = confidence
        outcome.business_value = BusinessValue.model_validate(bv_data)
    if step_id is not None:
        outcome.step_id = step_id
    return f"Customer outcome updated successfully: {outcome.model_dump_json()}"


@mcp.tool
def delete_customer_outcome(outcome_id: str) -> str:
    """Delete a Customer Outcome by ID."""
    if outcome_id not in customer_outcomes_db:
        return f"Error: Customer outcome with ID {outcome_id} not found."
    del customer_outcomes_db[outcome_id]
    return f"Customer outcome {outcome_id} deleted successfully."


@mcp.tool
def compute_opportunity(importance: float, satisfaction: float) -> str:
    """Compute ODI Opportunity Score: importance + max(importance - satisfaction, 0)."""
    if not (1.0 <= importance <= 10.0 and 1.0 <= satisfaction <= 10.0):
        return "Error: importance and satisfaction must be between 1 and 10."
    return f"Opportunity Score = {compute_opportunity_score(importance, satisfaction):.2f}"


@mcp.tool
def get_outcomes(job_id: str) -> str:
    """Retrieve all Desired Outcomes for a specific Job."""
    if job_id not in jobs_db:
        return f"Error: Job with ID {job_id} not found."
    job_outcomes = [outcome for outcome in outcomes_db.values() if outcome.job_id == job_id]
    return f"[{', '.join(outcome.model_dump_json() for outcome in job_outcomes)}]"


@mcp.tool
def get_odi_framework_guidelines() -> str:
    """Returns the step-by-step ODI framework guidelines, explaining which tool to use at each stage of the process."""
    return (
        "## Outcome-Driven Innovation (ODI) — Stage-by-Stage Tool Guide\n\n"
        "Follow this sequence when guiding a user through the ODI process:\n\n"
        "### Stage 1: Define Intent (Job-to-be-Done)\n"
        "- **When**: Always start here if no Job exists.\n"
        "- **Ask the user**: 'What is the main task or goal your customer is trying to accomplish?'\n"
        "- **Tools to use**:\n"
        "  - `add_job(name, description)` — Create the Job once identified.\n"
        "  - `get_jobs()` — Check if a relevant Job already exists before creating a new one.\n"
        "  - `get_job(job_id)` — Retrieve details of a specific existing Job.\n\n"
        "### Stage 2: Capture Desired Outcomes\n"
        "- **When**: After a Job is defined. Outcomes come BEFORE steps or solutions.\n"
        "- **Ask the user**: 'What does success look like? What should happen faster, more reliably, or more consistently?'\n"
        "- **Outcome statement format**: 'Minimize/Maximize the [metric] when [context].'\n"
        "- **Tools to use**:\n"
        "  - `add_outcome(job_id, statement, importance, satisfaction)` — Capture each desired outcome with scores.\n"
        "  - `get_outcomes(job_id)` — Review all outcomes captured for a Job.\n\n"
        "### Stage 3: Calculate Opportunity Scores\n"
        "- **When**: After outcomes have importance and satisfaction scores.\n"
        "- **Formula**: Opportunity Score = importance + max(importance - satisfaction, 0)\n"
        "- **Scores > 10** indicate high innovation opportunity. Guide the user to focus efforts there.\n"
        "- **Tools to use**: `get_outcomes(job_id)` — Review opportunity_score field on each outcome.\n\n"
        "### Stage 4: Build the Job Map\n"
        "- **When**: After key outcomes are captured. Use to organize the job execution context.\n"
        "- **Ask the user**: 'What are the key phases or steps the customer takes when doing this job?'\n"
        "- **Tools to use**:\n"
        "  - `add_step(job_id, name, order)` — Add each chronological step.\n"
        "  - `get_job_map(job_id)` — View the complete ordered job map.\n\n"
        "### General Rule\n"
        "Never skip stages. Always confirm the user has a Job defined (Stage 1) before capturing Outcomes (Stage 2), "
        "and always capture Outcomes (Stage 2) before building the Job Map (Stage 4)."
    )


@mcp.tool
def get_capabilities() -> str:
    """Provides a human-friendly summary of the agent's capabilities and how to use them."""
    return (
        "Here is what I can help you with as your Agentic ODI assistant:\n\n"
        "🎯 **Manage Jobs-to-be-Done (JTBD)**: Add, list, and retrieve Jobs.\n"
        "🗺️ **Build Job Maps**: Break down a Job into ordered Steps.\n"
        "📊 **Track Desired Outcomes**: Record outcomes with importance/satisfaction scores and calculate Opportunity Scores.\n"
        "💼 **Manage Customer Outcomes**: Add, list, get, update, and delete Customer Outcomes linking customer value and business value.\n"
        "📖 **ODI Framework Guidelines**: Call `get_odi_framework_guidelines` to see which tool to use at each ODI stage.\n\n"
        "💡 **Tip**: Ask me to 'get started' and I will guide you step-by-step through the ODI process from intent to opportunity scoring!"
    )


@mcp.tool
def greet(name: str) -> str:
    """A simple test tool to verify the connection."""
    return f"Hello, {name}!"


def main() -> None:
    mcp.run(transport="http", port=8000)


if __name__ == "__main__":
    main()
