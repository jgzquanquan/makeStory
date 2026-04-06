# makeStory

`makeStory` 是一个面向短剧创作的多 Agent 剧本生成器。

它不是单次“出一段文本”的玩具，而是一个能看到过程的创作控制台。你可以先选热门题材，再配置模型，先测试 API 是否通，再实时观察创意池、故事 Bible、大纲审稿、分集规划和分集写作一步步推进。

## Overview

这个项目现在已经同时提供两套入口：

- `CLI`，适合命令行快速试跑
- `Web Console`，适合交互式配置、测试模型连接、观察实时进展
- `History Workspace`，适合在历史剧本之间搜索、排序、编辑标题备注、导出和继续改写

核心目标不是“随便生成一点剧情”，而是把短剧创作流程拆成多个明确的 Agent 环节，让输出更稳定，也让你更容易继续加新角色和新能力。

## What It Does

- 多 Agent 生成候选创意，不是一上来就押一个题材
- 自动挑选最优方向，并生成 `story_bible`
- 产出总大纲、人物小传、分集卡和分集剧本
- 审稿不通过时自动回到改写环节
- Web 控制台可以实时看进展，不再盲等
- 支持在生成前测试模型连接是否正常
- 历史剧本支持搜索、排序、软删除撤销、重新载入到表单
- 结果区支持 Markdown 阅读视图、目录导航、当前分集复制和 `MD/TXT/JSON` 导出

## Pipeline

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

## Why This Version Is Better

- Agent 已经按模块拆开，后面加 `Platform Adapter`、`Dialogue Doctor` 这种角色不会把代码堆成一团。
- JSON 类输出已经走 Pydantic 校验，真实模型返回脏数据时更容易发现问题。
- Web 页不是纯表单了，能看到每个阶段的实时状态。
- 模型配置支持单独测试连通性，少走一次完整长链路失败。

## Demo Flow

一次完整流程大致是这样：

1. 选择题材预设，比如都市情感、豪门复仇、职场逆袭
2. 配置模型、`API Key`、`Base URL`
3. 先点击“测试模型连接”
4. 发起生成任务
5. 实时观察每个阶段推进
6. 查看最终创意、Bible、分集卡和分集文本

## Project Structure

`make_story/agents/`
各 Agent 独立模块，按职责拆分为创意、选择、大纲、审稿、改写、分集规划、分集写作。

`make_story/schemas.py`
结构化产物定义，包含创意候选、故事 bible、审稿结果、分集卡等 schema。

`make_story/state.py`
全局状态定义。

`make_story/service.py`
流程调度、进度回调、模型测试、结果序列化。

`make_story/web.py`
本地 Web 服务、任务状态接口、静态资源分发和历史接口会话校验。

`make_story/webapp/index.html`
前端页面壳和样式。

`make_story/webapp/app.js`
前端主状态层、事件绑定、局部渲染和轮询控制。

`make_story/webapp/api.js`
前端请求层，包含轻量错误分类和历史接口 session 头注入。

`make_story/webapp/dom.js`
前端 DOM 引用收口。

`make_story/webapp/markdown.js`
Markdown 构建、目录生成、渲染和导出文本拼装。

`make_story/run.py`
CLI 入口。

## Requirements

- Python 3.10+
- 一个可用的 OpenAI 兼容模型接口，或者直接用 `--mock`
- 推荐使用项目内的 `.conda` Python 环境运行

## Quick Start

### 1. 安装依赖

```bash
./.conda/bin/pip install -r requirements.txt
```

### 2. Mock 模式先跑通

```bash
./.conda/bin/python -m make_story.run --topic "都市情感悬疑" --constraints "女性向短剧，6集，每集3分钟" --mock
```

### 3. 启动 Web 控制台

```bash
./.conda/bin/python -m make_story.web --host 127.0.0.1 --port 8000
```

打开：

```text
http://127.0.0.1:8000
```

### 4. 使用真实模型

在 `.env` 里配置：

```bash
OPENAI_API_KEY=your_key
MODEL_NAME=gpt-4o-mini
BASE_URL=
```

如果你接的是兼容 OpenAI 的中转服务，也可以直接在 Web 控制台里填写 `Base URL` 和模型名。

## CLI Usage

基础示例：

```bash
./.conda/bin/python -m make_story.run \
  --topic "豪门复仇反转" \
  --constraints "竖屏短剧，8集，每集3分钟，前三集必须有强反转"
```

常用参数：

- `--topic`：主题或题材关键词
- `--constraints`：平台、受众、节奏、时长等要求
- `--num-episodes`：分集数
- `--max-iterations`：审稿最大迭代次数
- `--mock`：不调用真实模型，走 Mock 流程

## Web Console

当前页面支持：

- 热门题材预设
- `OPENAI_API_KEY` / `MODEL_NAME` / `BASE_URL` 配置
- 模型连接测试
- 实时阶段进展
- 生成后查看最佳创意、故事 Bible、分集规划和剧本文本
- 历史剧本标题搜索、排序、删除与撤销删除
- 历史剧本重新载入到生成表单
- 历史剧本标题与备注编辑
- Markdown 阅读视图、目录导航、复制当前分集 Markdown
- 导出 `MD` / `TXT` / `JSON`

当前页面的阶段面板包含：

- 创意池
- 选题与 Bible
- 大纲设计
- 审稿迭代
- 分集规划
- 分集写作

## Model Compatibility

当前后端使用的是 OpenAI Python SDK，所以兼容以下两类接口：

- OpenAI 官方接口
- OpenAI-compatible 接口，只要支持 `chat.completions.create`

如果你接阿里云、硅基流动或其他兼容接口，通常只需要改：

- `BASE_URL`
- `MODEL_NAME`
- `OPENAI_API_KEY`

## Architecture Notes

当前服务层主要在 `make_story/service.py`：

- `run_pipeline()` 负责串起全部 Agent
- `test_model_connection()` 负责做模型可用性探针
- 进度事件通过 `ProgressEvent` 回传给 Web 任务状态接口

Web 层在 `make_story/web.py`：

- `/api/test-model`：测试模型连接
- `/api/generate`：创建生成任务
- `/api/jobs/{job_id}`：轮询任务进展
- `/api/stories`：历史列表、标题搜索、排序和分页
- `/api/stories/{id}`：历史详情
- `/api/stories/{id}/meta`：标题和备注更新
- `/api/stories/{id}/restore`：撤销软删除

## Frontend Notes

当前 Web 控制台已经从单文件内联脚本拆成多个前端模块，重点解决的是“结果区切换卡”和“轮询空转”：

- 结果区改成稳定壳子 + 局部更新，切分集时不再整块重建
- 轮询会对 `progress` / `preview` 做脏检查，没变化就跳过渲染
- Markdown 阅读区做了故事级缓存和分集级更新
- 历史列表和结果区高频按钮改成事件委托，减少重复绑监听
- 主要视觉效果降级，保留层次感，但减少 `backdrop-filter` 带来的重绘成本

如果你要继续扩展页面，优先沿着 `app.js` / `api.js` / `markdown.js` 这条拆分继续走，不要把逻辑再塞回 `index.html`。

## Local Tool Boundary

当前 Web 控制台按“本地单用户工具”设计，不是多用户在线服务。

- 历史接口需要页面注入的轻量 session token
- 标题、备注和剧本文本都按纯文本处理，不接受用户自定义 HTML 或 Markdown 直通
- UI 保存的模型配置会写入本地 `.env`

不要在共享机器或公共环境里把它当成生产后台使用。

## Troubleshooting

### 页面能打开，但生成失败

先用“测试模型连接”按钮。这个按钮会比完整生成更快暴露问题。

重点检查：

- `API Key` 是否有效
- `Base URL` 是否正确
- `MODEL_NAME` 是否存在于你当前服务商

如果生成过程中页面提示任务状态过期，当前版本会优先尝试从历史记录恢复，你可以直接在历史区打开最近生成的剧本。

### CLI 报缺少依赖

说明你当前 Python 环境没装依赖。优先用项目内 `.conda` 环境。

```bash
./.conda/bin/pip install -r requirements.txt
```

### GitHub 推送失败

这个仓库已经切到 SSH 方案。后续机器上如果要 push，记得先配置 GitHub SSH key。

## Roadmap

- 增加 `Platform Adapter Agent`，分别优化抖音、快手、微信小程序短剧节奏
- 增加 `Dialogue Doctor Agent`，单独强化对白 punchline
- 增加 `Consistency Agent`，检查人物动机、线索回收和设定一致性
- 为 Web 控制台补最小前端回归测试，覆盖历史页、结果页和恢复路径
- 继续打磨 Markdown 阅读区，例如目录定位和当前分集复制体验
- 把文本大纲和剧本也升级成更稳定的结构化中间层

## License

如果你准备开源，下一步建议补一个正式 `LICENSE` 文件。现在仓库里还没有。
