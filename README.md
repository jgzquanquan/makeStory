# makeStory

一个面向“自动生成剧本”的多 Agent 短剧生成原型。

当前版本不再只是串行 demo，而是整理成了清晰的创作流水线：

1. `Ideation Agents`
并行模拟多个创意角色，生成候选题材池。

2. `Showrunner / Selector`
从候选题材中选出最优方向，并产出 `story_bible`。

3. `Outline Agent`
把故事 bible 扩展成总大纲和人物小传。

4. `Review Agent`
从钩子、节奏、角色驱动、平台适配和合规角度审稿。

5. `Rewrite Agent`
根据审稿意见迭代大纲。

6. `Episode Planner`
先生成每集功能卡，再进入正片写作。

7. `Episode Writer`
按分集卡产出每集剧本。

## 当前架构特点

- 每个 Agent 都在独立模块里，便于继续扩展新角色。
- JSON 类 Agent 已增加 Pydantic schema 校验，减少真实模型输出波动导致的流程失稳。
- 关键编排节点会显式检查异常情况，例如空创意池、选中不存在的标题、分集卡数量不匹配。

## 项目结构

`make_story/schemas.py`
结构化产物定义：创意候选、故事 bible、审稿结果、分集卡。

`make_story/state.py`
LangGraph 状态定义。

`make_story/agents/`
各 Agent 独立模块，按职责拆分为创意、选择、大纲、审稿、改写、分集规划、分集写作。

`make_story/graph.py`
多 Agent 编排。

`make_story/run.py`
CLI 入口。

## 运行

```bash
./.conda/bin/python -m make_story.run --topic "都市情感悬疑" --constraints "女性向短剧，6集，每集3分钟" --mock
```

## Web 控制台

项目现在带一个本地前端操作页，可以：

- 选择热门主题预设
- 配置 `OPENAI_API_KEY`
- 配置 `MODEL_NAME`
- 配置 `BASE_URL`
- 直接触发剧本生成并查看结果

启动方式：

```bash
./.conda/bin/python -m make_story.web --host 127.0.0.1 --port 8000
```

如果使用真实模型，请配置 `.env`：

```bash
OPENAI_API_KEY=your_key
MODEL_NAME=gpt-4o-mini
BASE_URL=
```

## 下一步建议

- 增加 `Platform Adapter Agent`，分别优化抖音/快手/微信小程序短剧节奏。
- 增加 `Dialogue Doctor Agent`，专门做台词 punchline 强化。
- 增加 `Consistency Agent`，检查人物动机、设定和线索回收。
- 把每个 Agent 的输出改成严格 schema 校验，减少自由文本解析。
