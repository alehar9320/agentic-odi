import uuid
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from fastmcp import FastMCP

mcp = FastMCP("Agentic ODI Server")

# --- Pydantic Models for ODI Artifacts ---

class Job(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., description="The name of the Job-to-be-Done")
    description: Optional[str] = Field(None, description="Detailed description of the Job")

class Step(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    job_id: str = Field(..., description="The ID of the Job this step belongs to")
    name: str = Field(..., description="The name of the job step")
    order: int = Field(..., description="The chronological order of this step in the job map")

class Outcome(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    job_id: str = Field(..., description="The ID of the Job this outcome relates to")
    step_id: Optional[str] = Field(None, description="The ID of the specific Step, if applicable")
    statement: str = Field(..., description="The desired outcome statement (e.g., 'Minimize the time it takes to...')")
    importance: Optional[float] = Field(None, ge=1.0, le=10.0, description="Importance score (1-10)")
    satisfaction: Optional[float] = Field(None, ge=1.0, le=10.0, description="Current satisfaction score (1-10)")
    opportunity_score: Optional[float] = Field(None, description="Opportunity score (Importance + max(Importance - Satisfaction, 0))")

# --- In-Memory Storage ---
# For sandbox testing. In production, connect to a rigorous database.
jobs_db: Dict[str, Job] = {}
steps_db: Dict[str, Step] = {}
outcomes_db: Dict[str, Outcome] = {}

# --- MCP Tools ---

@mcp.tool
def add_job(name: str, description: str = None) -> str:
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
def add_outcome(job_id: str, statement: str, step_id: str = None, importance: float = None, satisfaction: float = None) -> str:
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
        opportunity_score=op_score
    )
    outcomes_db[outcome.id] = outcome
    return f"Outcome created successfully: {outcome.model_dump_json()}"

@mcp.tool
def get_outcomes(job_id: str) -> str:
    """Retrieve all Desired Outcomes for a specific Job."""
    if job_id not in jobs_db:
         return f"Error: Job with ID {job_id} not found."
    job_outcomes = [outcome for outcome in outcomes_db.values() if outcome.job_id == job_id]
    return f"[{', '.join(outcome.model_dump_json() for outcome in job_outcomes)}]"

@mcp.tool
def greet(name: str) -> str:
    """A simple test tool to verify the connection."""
    return f"Hello, {name}!"

if __name__ == "__main__":
    mcp.run(transport="http", port=8000)