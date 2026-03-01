import asyncio
from fastmcp import Client
from my_server import mcp

async def main():
    async with Client(mcp) as client:
        # Run add_job and examine result object
        job_result = await client.call_tool("add_job", {"name": "Test", "description": "123"})
        print("Type:", type(job_result))
        print("Dir:", dir(job_result))
        try:
            print("Dict:", job_result.__dict__)
        except:
            pass
        if hasattr(job_result, 'content'):
            print("Content type:", type(job_result.content))
            print("Content values:", job_result.content)
            print("Text:", job_result.content[0].text)
        elif isinstance(job_result, list):
            print("List length:", len(job_result))
            print("First item text:", getattr(job_result[0], 'text', None))

if __name__ == "__main__":
    asyncio.run(main())
