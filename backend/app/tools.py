import pyautogui
import webbrowser
import datetime
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    Registry for OS-level and knowledge-based tools.
    Provides generic schemas for universal LLM tool-calling.
    """

    def __init__(self):
        # Generic Tool Definitions
        self.tools = [
            {
                "name": "spotify_control",
                "description": "Control music playback on the user's PC (Spotify/Media Keys).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": [
                                "play",
                                "pause",
                                "next",
                                "previous",
                                "volume_up",
                                "volume_down",
                            ],
                            "description": "The media control action to perform.",
                        }
                    },
                    "required": ["action"],
                },
            },
            {
                "name": "search_web",
                "description": "Open a URL or search query in the default web browser.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query or URL to open.",
                        }
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "get_time",
                "description": "Get the current local time.",
                "parameters": {"type": "object", "properties": {}},
            },
            {
                "name": "recall_memory",
                "description": "Search long-term memory for specific details about the user or past conversations.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query to find relevant memories.",
                        }
                    },
                    "required": ["query"],
                },
            },
        ]

        self.memory_store = None

    def set_memory_store(self, memory_store):
        self.memory_store = memory_store

    def get_definitions(self) -> List[Dict[str, Any]]:
        """Returns the list of tool definitions for LLM context."""
        return self.tools

    async def execute(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Executes a tool by name with provided arguments."""
        logger.info(f"🛠️ Mesh Tool Call: {name} | Args: {args}")

        try:
            if name == "spotify_control":
                action = args.get("action")
                if action in ["play", "pause"]:
                    pyautogui.press("playpause")
                elif action == "next":
                    pyautogui.press("nexttrack")
                elif action == "previous":
                    pyautogui.press("prevtrack")
                elif action == "volume_up":
                    pyautogui.press("volumeup")
                elif action == "volume_down":
                    pyautogui.press("volumedown")
                return {"result": f"Executed {action}"}

            elif name == "search_web":
                query = args.get("query")
                if query.startswith("http"):
                    webbrowser.open(query)
                else:
                    webbrowser.open(f"https://www.google.com/search?q={query}")
                return {"result": f"Opened browser for: {query}"}

            elif name == "get_time":
                now = datetime.datetime.now().strftime("%I:%M %p")
                return {"result": f"Current time is {now}"}

            elif name == "recall_memory":
                if not self.memory_store:
                    return {"error": "Memory store not available."}

                query = args.get("query")
                results = await self.memory_store.search_memories(query)
                if not results:
                    return {"result": "No relevant memories found."}
                return {"result": f"Found memories: {', '.join(results)}"}

        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            return {"error": str(e)}

        return {"error": f"Tool '{name}' not found"}
