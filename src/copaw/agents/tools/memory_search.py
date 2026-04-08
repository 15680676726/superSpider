# -*- coding: utf-8 -*-
"""Memory search tool for lexical search in memory files."""
from agentscope.tool import ToolResponse
from agentscope.message import TextBlock


def create_memory_search_tool(memory_runtime):
    """Create a memory_search tool function with bound private memory runtime.

    Args:
        memory_runtime: Private compaction/search runtime to use for searching

    Returns:
        An async function that can be registered as a tool
    """

    async def memory_search(
        query: str,
        max_results: int = 5,
        min_score: float = 0.1,
    ) -> ToolResponse:
        """
        Search MEMORY.md and memory/*.md files lexically.

        Use this tool before answering questions about prior work, decisions,
        dates, people, preferences, or todos. Returns top relevant snippets
        with file paths and line numbers.

        Args:
            query (`str`):
                The query used to find relevant memory snippets.
            max_results (`int`, optional):
                Maximum number of search results to return. Defaults to 5.
            min_score (`float`, optional):
                Minimum similarity score for results. Defaults to 0.1.

        Returns:
            `ToolResponse`:
                Search results formatted with paths, line numbers, and content.
        """
        if memory_runtime is None:
            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text="Error: Private conversation compaction is not enabled.",
                    ),
                ],
            )

        try:
            return await memory_runtime.memory_search(
                query=query,
                max_results=max_results,
                min_score=min_score,
            )

        except Exception as e:
            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text=f"Error: Memory search failed due to\n{e}",
                    ),
                ],
            )

    return memory_search
