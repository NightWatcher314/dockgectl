# dockgectl

[English](README.md) | [中文](README-zh.md)

`dockgectl` 是一个通过 Dockge Web UI 使用的 Socket.IO 协议自动化管理 [Dockge](https://github.com/louislam/dockge) 的 Python CLI。

`dockgectl` 是一个 AI-native 运维项目。仓库内置了 Codex skill：[`skills/dockge/SKILL.md`](skills/dockge/SKILL.md)，让 AI agent 可以按照明确的安全规则、命令形状和验证步骤管理 Dockge，而不是临时猜测原始 Socket.IO 事件。

它重点覆盖 Dockge stack 工作流：列出和查看 stacks，保存和部署 compose 文件，执行 stack 生命周期操作，查看服务状态，重启服务，列出 Dockge 暴露的 Docker networks，以及把 `docker run` 命令转换成 Compose YAML。

Dockge 目前没有为 stack 管理提供完整、公开、稳定的 REST API。`dockgectl` 封装的是 Dockge 1.x 内部 Socket.IO 事件，当前已在 Dockge `1.5.1-nightwatcher.0` 上测试通过；不保证兼容其他 Dockge 版本。旧版 Dockge 会安全忽略 dockgectl 的握手提示，并保持原有的 eager Agent 行为。

## AI-Native Skill

内置的 `dockge` skill 会指导 agent 把 `dockgectl` 作为 Dockge 变更的稳定执行器。

skill 中编码的关键规则：

- 精确状态检查使用 `dockgectl ... -o json`。
- 不要把真实 token、密码或私有实例 URL 写进文档和命令示例。
- 优先使用已支持的 `dockgectl` 命令，而不是直接调用原始 Socket.IO 事件。
- `stack stop`、`stack down`、`stack delete`、覆盖式 `stack deploy` 等影响服务的操作必须有明确用户意图。
- 覆盖已有 stack 前，先结构化比较 Compose。Compose 可能含明文凭据时，将 `stack diff` 视为含密输出。
- 使用 `dockgectl stack apply --verify` 完成 save/deploy 后的 stack 与 service 轮询验证，但必须先写入 mode-0600 临时文件，只输出白名单验证字段。
- stack 变更后使用 `dockgectl stack get NAME -o json` 验证；服务级变更后使用 `dockgectl service status NAME -o json` 验证。
- 将原始 `stack get` / `stack ps` JSON 视为可能含密钥的输出，因为其中可能包含 Compose 和 `composeENV`；只允许写入受保护临时文件，并仅显示白名单字段。
- 应用已有 stack 前，按 YAML 字段路径建立结构化白名单；任何非目标字段变化都必须中止。

## 安装

使用 Homebrew：

```bash
brew tap NightWatcher314/homebrew-formula
brew install dockgectl
```

使用 uv 从 PyPI 安装：

```bash
uv tool install dockgectl
```

开发环境：

```bash
UV_NO_CONFIG=1 UV_DEFAULT_INDEX=https://pypi.org/simple uv sync --locked
UV_NO_CONFIG=1 UV_DEFAULT_INDEX=https://pypi.org/simple uv run --locked dockgectl --help
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

`--tail` 从 dockgectl 0.2.3 起受支持。旧版二进制不接受该参数时，使用 `dockgectl stack logs app | tail -n 200`，或先检查 `dockgectl stack logs --help` 再升级。

预览、保存、部署或应用 stack：

```bash
dockgectl stack plan app -f compose.yml --env-file .env
dockgectl stack diff app -f compose.yml --env-file .env
dockgectl stack save app -f compose.yml --env-file .env --yes
dockgectl stack deploy app -f compose.yml --env-file .env --yes
dockgectl stack apply app -f compose.yml --env-file .env --yes --health-url https://app.example.com/health -o json
```

`stack save`、`stack deploy` 和 `stack apply` 覆盖已有 stack 前会确认；明确需要自动化时使用 `--yes`。使用 `--dry-run` 只输出计划不修改 Dockge。省略 `--env-file` 会保留 stack 现有 env；只有显式传入空 env 文件才会清空。变更后 dockgectl 会重新读取 stack，核对提交的 env 是否真正持久化。`stack diff` 默认只脱敏疑似 secret 的 env 值，不会脱敏 Compose 内的明文凭据；Compose 可能含 secret 时只能捕获到受保护文件，不能直接记录。`--include-env-values` 会输出原始 env diff，可能暴露密钥。`stack apply --verify` 支持 `-o json|yaml|table`，并会轮询 `stack get` 与 `service status`，但输出中的 `verification.stack` 包含完整 `composeYAML` 和 `composeENV`；必须先重定向到受保护文件，只输出 `applied`、`apply_error`、`verification.ok`、`verification.services` 和 `verification.health`。即使 Dockge Socket.IO 事件等待超时，也会继续用真实服务状态判断结果。服务验证会接受常见 Dockge/Docker 健康状态，例如 `running`、`healthy`、`started` 和 `up`。

应用变更后的 Compose 前，应结构化解析 live 与 proposed YAML，并只允许任务批准的字段路径变化，例如 `services.web.image`。发现任何其他字段变化时立即中止，并显式断言 Redis、Postgres 等依赖服务镜像保持不变。禁止使用宽泛正则做 service-scoped 修改。

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

在兼容的 Dockge 服务端上，CLI 会话只连接本次请求的 Agent；无关 Agent 离线不会
阻塞命令。只有只读 Agent 事件收到 Dockge 明确返回的 `AGENT_NOT_READY` 时才会重试
一次；普通 Socket.IO 超时和所有 stack/service 变更都不会自动重试。
`stack list --endpoint ENDPOINT` 也只等待目标 endpoint 对应的 `stackList` 推送。

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
