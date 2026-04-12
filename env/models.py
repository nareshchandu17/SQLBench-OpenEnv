from pydantic import BaseModel, Field
from typing import List, Optional, Any

class RewardBreakdown(BaseModel):
    syntax_penalty: float = 0.0
    result_match: float = 0.0
    column_match: float = 0.0
    row_count_match: float = 0.0
    efficiency_bonus: float = 0.0

class SQLObservation(BaseModel):
    task_id: str
    schema_ddl: str
    broken_query: str
    error_message: str
    expected_description: str
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

class TaskState(BaseModel):
    task_id: str
    schema_ddl: str
    broken_query: str
    ground_truth_query: str
    expected_result: Any
    step_count: int
    max_steps: int
    done: bool
    cumulative_reward: float
    previous_attempts: List[str]
