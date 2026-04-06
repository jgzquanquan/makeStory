SYSTEM_IDEATION = (
	"你是短剧项目的创意总监团队。你需要以多个不同创作 Agent 的视角并行产出候选创意。"
)

SYSTEM_CRITIC = (
	"你是一位严格的内容审稿编辑，关注剧情逻辑、市场度、情绪价值和合规风险。"
)

SYSTEM_ARCHITECT = (
	"你是短剧主编剧兼 showrunner，负责把创意整合成可执行的故事 bible、角色关系和分集推进。"
)

IDEATION_USER_TMPL = (
	"给定主题: {topic}\n"
	"受众/平台约束: {constraints}\n"
	"请模拟 3 个不同 Agent 并行产出创意：市场热点 Agent、情绪关系 Agent、爽点结构 Agent。\n"
	"输出 JSON 对象，格式如下：\n"
	'{{"idea_candidates":[{{"agent_name":"","title":"","logline":"","target_audience":"","selling_points":[""],"risks":[""]}}]}}\n'
)

SELECT_USER_TMPL = (
	"以下是多 Agent 给出的创意候选：\n{ideas}\n\n"
	"请选出最适合做成系列短剧的方案，并扩展成故事 bible。\n"
	"输出 JSON 对象，格式如下：\n"
	'{{"selected_title":"","selection_reason":"","story_bible":{{"world":"","core_conflict":"","theme":"","tone":"","main_characters":[""],"episode_arcs":[""]}}}}'
)

OUTLINE_USER_TMPL = (
	"基于以下故事 bible 生成短剧总大纲和人物小传。\n"
	"标题：{title}\n"
	"故事 bible：\n{story_bible}\n\n"
	"输出格式：\n"
	"[大纲]\n1. ...\n2. ...\n3. ...\n\n[人物]\n- 名字：目标、性格、秘密、关系张力\n"
)

REVIEW_USER_TMPL = (
	"请从以下维度审稿：钩子密度、角色驱动、反转节奏、合规风险、平台适配度。\n"
	"如果不通过，给出可执行修改意见。\n"
	"输出 JSON 对象：\n"
	'{{"approved":true,"issues":"","strengths":[""],"rewrite_focus":[""]}}\n'
)

REWRITE_OUTLINE_USER_TMPL = (
	"根据这些问题与建议，重写并改进大纲与人物。\n"
	"问题：{issues}\n"
	"优先修改方向：{rewrite_focus}\n"
	"保留核心卖点，提升节奏、冲突和角色动机，确保合规。"
)

EPISODE_PLAN_USER_TMPL = (
	"基于标题、故事 bible、大纲和人物设定，为 {num_episodes} 集短剧生成分集卡。\n"
	"标题：{title}\n"
	"故事 bible：\n{story_bible}\n\n"
	"大纲：\n{outline}\n\n"
	"人物：\n{characters}\n\n"
	"输出 JSON 对象，格式如下：\n"
	'{{"episode_plans":[{{"episode_number":1,"title":"","goal":"","hook":"","beats":[""]}}]}}\n'
)

EPISODE_USER_TMPL = (
	"请基于以下内容编写第 {index} 集剧本文本。\n"
	"本集分集卡：\n{episode_plan}\n\n"
	"要求：800-1500字，包含场景标识、动作、对白；结尾必须留下下一集钩子。"
)
