import json

import typer
from rich import print

from .service import GenerateRequest, persist_story, run_pipeline


app = typer.Typer(add_completion=False)


@app.command()
def generate(
	topic: str = typer.Option(..., help="主题或题材关键词"),
	constraints: str = typer.Option("", help="平台/受众/时长等约束"),
	num_episodes: int = typer.Option(6, help="分集数量"),
	max_iterations: int = typer.Option(2, help="大纲审稿最大迭代次数"),
	mock: bool = typer.Option(False, help="使用 Mock LLM，无需 API Key"),
):
	state = run_pipeline(
		GenerateRequest(
		topic=topic,
		constraints=constraints,
		num_episodes=num_episodes,
		max_iterations=max_iterations,
			mock=mock,
		)
	)
	story_id = persist_story(
		GenerateRequest(
			topic=topic,
			constraints=constraints,
			num_episodes=num_episodes,
			max_iterations=max_iterations,
			mock=mock,
		),
		state,
	)

	print("\n[bold green]最佳创意[/bold green]\n")
	if state.selected_idea:
		print(f"标题: {state.selected_idea.title}")
		print(f"来源 Agent: {state.selected_idea.agent_name}")
		print(f"一句话梗概: {state.selected_idea.logline}")
	print(f"选择理由: {state.selection_reason}")

	print("\n[bold green]故事 Bible[/bold green]\n")
	print(json.dumps(state.story_bible.model_dump(), ensure_ascii=False, indent=2))
	print("\n[bold green]大纲[/bold green]\n")
	print(state.outline or "")
	print("\n[bold green]人物小传[/bold green]\n")
	print(state.characters or "")
	print("\n[bold green]分集规划[/bold green]\n")
	print(json.dumps([item.model_dump() for item in state.episode_plans], ensure_ascii=False, indent=2))
	print("\n[bold green]分集剧本：[/bold green]")
	for i, ep in enumerate(state.episodes, start=1):
		print(f"\n[bold]第{i}集[/bold]\n")
		print(ep)
	print(f"\n[bold cyan]已保存到历史库[/bold cyan] story_id={story_id}")


if __name__ == "__main__":
	app()
