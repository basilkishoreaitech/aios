import logging
from typing import Dict

logger = logging.getLogger(__name__)

class TokenBudgetExceededError(Exception):
    """Exception raised when an agent or pipeline exceeds its configured token budget."""
    pass

class TokenBudgetTracker:
    """Manages token budgets per agent and per-run to act as a cost control circuit breaker."""
    
    def __init__(self, global_limit: int = 500000):
        self.global_limit = global_limit
        self.total_consumed = 0
        self.agent_limits: Dict[str, int] = {}
        self.agent_consumed: Dict[str, int] = {}

    def set_agent_limit(self, agent_name: str, limit: int):
        """Set a budget limit for a specific agent."""
        self.agent_limits[agent_name] = limit
        if agent_name not in self.agent_consumed:
            self.agent_consumed[agent_name] = 0

    def consume(self, agent_name: str, tokens: int):
        """Register token consumption and check budget constraints."""
        if tokens <= 0:
            return

        # Check Global limit
        if self.total_consumed + tokens > self.global_limit:
            logger.critical(f"🚨 Token budget circuit breaker TRIPPED! Global budget {self.global_limit} exceeded.")
            raise TokenBudgetExceededError(
                f"Global token budget limit of {self.global_limit} exceeded. Outage recovery halted."
            )

        # Check Agent limit
        limit = self.agent_limits.get(agent_name, 15000)  # Default 15k if not configured
        consumed = self.agent_consumed.get(agent_name, 0)
        
        if consumed + tokens > limit:
            logger.warning(f"⚠️ Agent '{agent_name}' exceeded its token budget of {limit} (requested: {tokens}, used: {consumed}). Recording usage and continuing.")

        # Record consumption regardless — budget check is advisory, not a circuit-breaker for individual agents
        self.agent_consumed[agent_name] = consumed + tokens
        self.total_consumed += tokens
        logger.info(f"Agent '{agent_name}' consumed {tokens} tokens. (Total run usage: {self.total_consumed}/{self.global_limit})")

    def get_consumed(self, agent_name: str) -> int:
        """Get tokens consumed by a specific agent."""
        return self.agent_consumed.get(agent_name, 0)
