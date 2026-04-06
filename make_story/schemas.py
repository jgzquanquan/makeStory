from typing import List
from pydantic import BaseModel, Field, model_validator


class IdeaCandidate(BaseModel):
	agent_name: str
	title: str
	logline: str
	target_audience: str = ""
	selling_points: List[str] = Field(default_factory=list)
	risks: List[str] = Field(default_factory=list)


class StoryBible(BaseModel):
	world: str = ""
	core_conflict: str = ""
	theme: str = ""
	tone: str = ""
	main_characters: List[str] = Field(default_factory=list)
	episode_arcs: List[str] = Field(default_factory=list)


class IdeationResponse(BaseModel):
	idea_candidates: List[IdeaCandidate] = Field(default_factory=list)

	@model_validator(mode="after")
	def validate_candidates(self) -> "IdeationResponse":
		if not self.idea_candidates:
			raise ValueError("至少需要一个创意候选")
		return self


class SelectionResponse(BaseModel):
	selected_title: str
	selection_reason: str
	story_bible: StoryBible


class OutlineReview(BaseModel):
	approved: bool = False
	issues: str = ""
	strengths: List[str] = Field(default_factory=list)
	rewrite_focus: List[str] = Field(default_factory=list)

	@model_validator(mode="after")
	def validate_review(self) -> "OutlineReview":
		is_empty_initial = (
			not self.approved
			and not self.issues.strip()
			and not self.strengths
			and not self.rewrite_focus
		)
		if not is_empty_initial and not self.approved and not self.issues.strip():
			raise ValueError("审稿不通过时必须提供 issues")
		return self


class EpisodePlan(BaseModel):
	episode_number: int
	title: str
	goal: str
	hook: str
	beats: List[str] = Field(default_factory=list)


class EpisodePlanResponse(BaseModel):
	episode_plans: List[EpisodePlan] = Field(default_factory=list)

	@model_validator(mode="after")
	def validate_plans(self) -> "EpisodePlanResponse":
		if not self.episode_plans:
			raise ValueError("至少需要一张分集卡")
		return self
