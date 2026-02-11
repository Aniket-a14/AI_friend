import pyautogui
import webbrowser
import datetime
import logging
import asyncio

logger = logging.getLogger(__name__)

class ToolRegistry:
    def __init__(self):
        # Definitions for Gemini
        self.definitions = [
            {
                "function_declarations": [
                    {
                        "name": "spotify_control",
                        "description": "Control music playback on the user's PC (Spotify/Media Keys).",
                        "parameters": {
                            "type": "OBJECT",
                            "properties": {
                                "action": {
                                    "type": "STRING",
                                    "description": "Action to perform: 'play', 'pause', 'next', 'previous', 'volume_up', 'volume_down'."
                                }
                            },
                            "required": ["action"]
                        }
                    },
                    {
                        "name": "search_web",
                        "description": "Open a URL or search query in the default web browser.",
                        "parameters": {
                            "type": "OBJECT",
                            "properties": {
                                "query": {
                                    "type": "STRING",
                                    "description": "The search query or URL to open."
                                }
                            },
                            "required": ["query"]
                        }
                    },
                    {
                        "name": "get_time",
                        "description": "Get the current local time.",
                    },
                    {
                        "name": "recall_memory",
                        "description": "Search long-term memory for specific details about the user or past conversations.",
                        "parameters": {
                            "type": "OBJECT",
                            "properties": {
                                "query": {
                                    "type": "STRING",
                                    "description": "The search query to find relevant memories."
                                }
                            },
                            "required": ["query"]
                        }
                    }
                ]
            }
        ]
        
        # We need access to the DB/MemoryStore. 
        # Ideally, this is injected or we pass the store instance to execute().
        self.memory_store = None

    def set_memory_store(self, memory_store):
        self.memory_store = memory_store

    async def execute(self, name, args):
        """Executes a tool by name with arguments."""
        logger.info(f"🛠️ Tool Call: {name} ({args})")
        
        try:
            if name == "spotify_control":
                # ... (keep existing) ...
                action = args.get("action")
                if action == "play" or action == "pause":
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
            
        return {"error": "Tool not found"}
