# dockgectl

[English](README.md) | [中文](README-zh.md)

`dockgectl` 是一个通过 Dockge Web UI 使用的 Socket.IO 协议自动化管理 [Dockge](https://github.com/louislam/dockge) 的 Python CLI。

`dockgectl` 是一个 AI-native 运维项目。仓库内置了 Codex skill：[`skills/dockge/SKILL.md`](skills/dockge/SKILL.md)，让 AI agent 可以按照明确的安全规则、命令形状和验证步骤管理 Dockge，而不是临时猜测原始 Socket.IO 事件。

它重点覆盖 Dockge stack 工作流：列出和查看 stacks，保存和部署 compose 文件，执行 stack 生命周期操作，查看服务状态，重启服务，列出 Dockge 暴露的 Docker networks，以及把 `docker run` 命令转换成 Compose YAML。

Dockge 目前没有为 stack 管理提供完整、公开、稳定的 REST API。`dockgectl` 封装的是 Dockge 1.x 内部 Socket.IO 事件，当前已在 Dockge `1.5.0` 上测试通过；不保证兼容其他 Dockge 版本。

## AI-Native Skill

内置的 `dockge` skill 会指导 agent 把 `dockgectl` 作为 Dockge 变更的稳定执行器。

skill 中编码的关键规则：

- 精确状态检查使用 `dockgectl ... -o json`。
- 不要把真实 token、密码或私有实例 URL 写进文档和命令示例。
- 优先使用已支持的 `dockgectl` 命令，而不是直接调用原始 Socket.IO 事件。
- `stack stop`、`stack down`、`stack delete`、覆盖式 `stack deploy` 等影响服务的操作必须有明确用户意图。
- 覆盖已有 stack 前，用 `dockgectl stack plan` / `dockgectl stack diff` 预览差异。
- 使用 `dockgectl stack apply --verify` 完成 save/deploy 后的 stack 与 service 轮询验证。
- stack 变更后使用 `dockgectl stack get NAME -o json` 验证；服务级变更后使用 `dockgectl service status NAME -o json` 验证。

## 安装

使用 Homebrew：

```bash
brew tap NightWatcher314/homebrew-formula
brew install dockgectl
```

开发环境：

```bash
uv sync
uv run dockgectl --help
```

## 配置

创建 profile 并登录：

```bash
dockgectl config profile add home --url https://dockge.example.com --use
dockgectl auth login --username admin
dockgectl auth status
```

单次命令指定 profile：

```bash
DOCKGECTL_PROFILE=home dockgectl stack list
```

查看当前配置和连通性：

```bash
dockgectl config get
dockgectl doctor -o json
dockgectl auth status -o json
```

常用环境变量：

```bash
DOCKGECTL_URL=https://dockge.example.com
DOCKGECTL_TOKEN=...
DOCKGECTL_USERNAME=admin
DOCKGECTL_PASSWORD=...
DOCKGECTL_ENDPOINT=
DOCKGECTL_INSECURE=1
```

## Stacks

列出并查看 stacks：

```bash
dockgectl stack list
dockgectl stack list --all-endpoints -o json
dockgectl stack get app -o json
dockgectl stack ps app
dockgectl stack logs app --tail 200
dockgectl stack logs app --follow --grep ERROR
```

预览、保存、部署或应用 stack：

```bash
dockgectl stack plan app -f compose.yml --env-file .env
dockgectl stack diff app -f compose.yml --env-file .env
dockgectl stack save app -f compose.yml --env-file .env --yes
dockgectl stack deploy app -f compose.yml --env-file .env --yes
dockgectl stack apply app -f compose.yml --env-file .env --yes --health-url https://app.example.com/health
```

`stack save`、`stack deploy` 和 `stack apply` 覆盖已有 stack 前会确认；明确需要自动化时使用 `--yes`。使用 `--dry-run` 只输出计划不修改 Dockge。`stack diff` 默认会脱敏疑似 secret 的 env 值；`--include-env-values` 会输出原始 env diff，可能暴露密钥。`stack apply --verify` 会轮询 `stack get` 与 `service status`；即使 Dockge Socket.IO 事件等待超时，也会继续用真实服务状态判断结果。服务验证会接受常见 Dockge/Docker 健康状态，例如 `running`、`healthy`、`started` 和 `up`。

执行 stack 操作：

```bash
dockgectl stack start app
dockgectl stack stop app --yes
dockgectl stack restart app
dockgectl stack update app
dockgectl stack down app --yes
dockgectl stack delete app --yes
```

指定已有 Dockge agent endpoint：

```bash
dockgectl agent list
dockgectl stack list --endpoint remote.example.com
dockgectl stack logs app --endpoint remote.example.com
```

`stack list --endpoint ENDPOINT` 会在 Dockge `requestStackList` agent 事件短暂超时
时重试一次，并且只等待与目标 endpoint 匹配的 `stackList` 推送。如果其他 endpoint
先推送了 stack list，会忽略这些推送，直到目标 endpoint 响应或命令超时。

## 服务

查看并管理 stack 内的服务：

```bash
dockgectl service status app -o json
dockgectl service status app --all-endpoints -o json
dockgectl service start app web
dockgectl service stop app web --yes
dockgectl service restart app web
```

## Networks 和 Composerize

```bash
dockgectl network list
dockgectl composerize 'docker run --name web nginx:alpine'
```

## 认证与存储

默认情况下，`dockgectl` 保存 Dockge JWT token，但不保存密码。若要把密码保存到当前 profile：

```bash
DOCKGECTL_PASSWORD='...' dockgectl auth login --username admin --save-password
```

之后可以复用保存的密码登录：

```bash
dockgectl auth login --use-saved-password
```

配置文件位于 `~/.config/dockgectl/config.json`，会尽量设置为 `0600` 权限，但保存的密码仍然是明文。只应在可信机器上使用 `--save-password`。

## 开源协议

MIT
