import asyncio
import logging
from enum import Enum
from typing import List, Callable, Any

logger = logging.getLogger(__name__)

class NodeStatus(Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    RUNNING = "RUNNING"

class Node:
    """Base Behavior Tree Node"""
    def __init__(self, name: str):
        self.name = name

    async def tick(self, blackboard: Any) -> NodeStatus:
        raise NotImplementedError("Each node must implement tick()")

class Composite(Node):
    """Base for nodes with multiple children (Selector, Sequence)"""
    def __init__(self, name: str, children: List[Node]):
        super().__init__(name)
        self.children = children

class Selector(Composite):
    """Returns SUCCESS if any child succeeds. Continues on FAILURE."""
    async def tick(self, blackboard: Any) -> NodeStatus:
        for child in self.children:
            status = await child.tick(blackboard)
            if status in [NodeStatus.SUCCESS, NodeStatus.RUNNING]:
                return status
        return NodeStatus.FAILURE

class Sequence(Composite):
    """Returns FAILURE if any child fails. Continues on SUCCESS."""
    async def tick(self, blackboard: Any) -> NodeStatus:
        for child in self.children:
            status = await child.tick(blackboard)
            if status in [NodeStatus.FAILURE, NodeStatus.RUNNING]:
                return status
        return NodeStatus.SUCCESS

class Action(Node):
    """Leaf node that performs an operation"""
    def __init__(self, name: str, func: Callable[[Any], Any]):
        super().__init__(name)
        self.func = func

    async def tick(self, blackboard: Any) -> NodeStatus:
        try:
            if asyncio.iscoroutinefunction(self.func):
                result = await self.func(blackboard)
            else:
                result = self.func(blackboard)
            return NodeStatus.SUCCESS if result else NodeStatus.FAILURE
        except Exception as e:
            logger.error(f"Action {self.name} failed: {e}")
            return NodeStatus.FAILURE

class Condition(Node):
    """Leaf node that checks a state"""
    def __init__(self, name: str, func: Callable[[Any], bool]):
        super().__init__(name)
        self.func = func

    async def tick(self, blackboard: Any) -> NodeStatus:
        result = self.func(blackboard)
        return NodeStatus.SUCCESS if result else NodeStatus.FAILURE
