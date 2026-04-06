from typing import List, Optional
from pydantic import BaseModel, Field
from .config import DEFAULT_MAX_ITERATIONS, DEFAULT_NUM_EPISODES
from .schemas import EpisodePlan, IdeaCandidate, OutlineReview, StoryBible


class PipelineState(BaseModel):
	# 输入
	topic: str
	constraints: str = ""

	# 多 Agent 创意阶段
	ideas: List[IdeaCandidate] = Field(default_factory=list)
	selected_idea: Optional[IdeaCandidate] = None
	selection_reason: str = ""

	# 故事设计
	story_bible: StoryBible = Field(default_factory=StoryBible)
	outline: Optional[str] = None
	characters: Optional[str] = None
	review: OutlineReview = Field(default_factory=OutlineReview)

	# 迭代控制
	iteration: int = 0
	max_iterations: int = DEFAULT_MAX_ITERATIONS

	# 分集
	episode_plans: List[EpisodePlan] = Field(default_factory=list)
	num_episodes: int = DEFAULT_NUM_EPISODES
	episodes: List[str] = Field(default_factory=list)

	def approved(self) -> bool:
		return self.review.approved

