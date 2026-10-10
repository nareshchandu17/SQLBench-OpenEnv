from pydantic import BaseModel, Field
from typing import List, Optional, Any

class RewardBreakdown(BaseModel):
    syntax_penalty: float = 0.0
    result_match: float = 0.0
    column_match: float = 0.0
    row_count_match: float = 0.0
    efficiency_bonus: float = 0.0

class SQLObservation(BaseModel):
    """
    Public observation exposed to the agent.
    
    SECURITY: This model MUST NEVER contain:
    - ground_truth_query
    - expected_result
    
    These are kept private in TaskState and only used by the grader.
    """
    task_id: str
    schema_ddl: str
    broken_query: str
    error_message: str
    expected_description: str  # Human-readable description, not the actual query
    step_count: int
    max_steps: int
    previous_attempts: List[str]
    last_execution_result: Optional[Any] = None

class SQLAction(BaseModel):
    query: str = Field(..., description="The corrected SQL query to execute")

class SQLReward(BaseModel):
    value: float
    breakdown: RewardBreakdown
    done: bool
    success: bool

class PublicTaskState(BaseModel):
    """
    Public state that can be safely exposed to agents.
    
    SECURITY: This model MUST NEVER contain:
    - ground_truth_query
    - expected_result
    
    These are only in the private TaskState used by the evaluator.
    """
    task_id: str
    schema_ddl: str
    broken_query: str
    step_count: int
    max_steps: int
    done: bool
    cumulative_reward: float
    previous_attempts: List[str]

class TaskState(PublicTaskState):
    """
    Private internal state used by the environment.
    
    Contains ground truth data that MUST NEVER be exposed to agents.
    Only the grader and reward computation should access these fields.
    """
    ground_truth_query: str  # The correct SQL query (PRIVATE)
    expected_result: Any  # The expected query result (PRIVATE)
