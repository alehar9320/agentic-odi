import pytest
from fastmcp import Client

from my_server import mcp


@pytest.mark.asyncio
async def test_add_job_returns_content():
    """Test that add_job returns a valid response with accessible content."""
    async with Client(mcp) as client:
        result = await client.call_tool("add_job", {"name": "Test", "description": "123"})

        assert hasattr(result, "content"), "Result should have a 'content' attribute"
        assert len(result.content) > 0, "Content should not be empty"
        assert result.content[0].text is not None, "First content item should have text"
        assert "Job created successfully" in result.content[0].text
