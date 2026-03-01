import asyncio
import json
import re
from fastmcp import Client

client = Client("http://localhost:8000/mcp")

def extract_id(result_str):
    match = re.search(r'"id"\s*:\s*"([^"]+)"', str(result_str))
    return match.group(1) if match else None

async def run_odi_workflow():
    async with client:
        print("--- Testing ODI MCP Tools ---")
        
        # 1. Add a Job
        print("\n[Client] Adding Job...")
        job_result = await client.call_tool("add_job", {"name": "Listen to music", "description": "Listen to music on the go"})
        print(job_result)
        
        job_id = extract_id(job_result)
        if not job_id:
             print("Failed to parse job_id.")
             return

        # 2. Add Steps to the Job Map
        print("\n[Client] Adding Steps...")
        step1_res = await client.call_tool("add_step", {"job_id": job_id, "name": "Select music", "order": 1})
        step2_res = await client.call_tool("add_step", {"job_id": job_id, "name": "Play music", "order": 2})
        print(step1_res)
        print(step2_res)
        
        step1_id = extract_id(step1_res)

        # 3. Add an Outcome
        print("\n[Client] Adding Outcomes...")
        outcome_res = await client.call_tool("add_outcome", {
             "job_id": job_id,
             "statement": "Minimize the time it takes to find a specific song",
             "importance": 8.5,
             "satisfaction": 4.0,
             "step_id": step1_id
        })
        print(outcome_res)

        # 4. Retrieve Data
        print("\n[Client] Retrieving Job Map...")
        job_map = await client.call_tool("get_job_map", {"job_id": job_id})
        print(job_map)

        print("\n[Client] Retrieving Outcomes...")
        outcomes = await client.call_tool("get_outcomes", {"job_id": job_id})
        print(outcomes)

if __name__ == "__main__":
    asyncio.run(run_odi_workflow())
