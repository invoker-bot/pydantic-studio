# 多会话 Embed Manager 实施计划

> 设计规格见 HFT 侧 `HFT-Python/docs/specs/2026-07-01-serve-config-studio-embed-design.md`(跨 repo 设计的 studio 部分)。

## 目标

在已交付的**单会话** embed 基座(`EditSession` / `mount_html_app` / base-path / `frontend/src/api/base.ts`,由 `2026-06-30-embeddable-renderers.md` 完成并已实现)之上,加一层**多会话**管理:`StudioEmbedManager` 让一个挂载点按 session id 隔离并发编辑,宿主(如 hft serve)拥有生命周期。这是通用库能力,不含任何 HFT 专属逻辑。

## 建立在已实现基座上(勿重造)

以下已在 `src` 中实现,**直接复用**:`EditSession`(`src/pydantic_studio/session.py`,带 `submit()`/`cancel()`/`outcome`/`readonly_paths`)、`StudioServer`(`renderers/html/server.py:45`,接受 `session=` 或 `tree=`,`base_path=` 参数)、`normalize_base_path`/`render_spa_index`(注入 `window.__PYDANTIC_STUDIO__={"basePath":...}` + 重写 asset URL)、`mount_html_app`、`frontend/src/api/base.ts` 的 `studioUrl()`。前一版计划**明确把多会话/auth 排除在外**——正是本计划的 delta。

## 关键设计点与防回归

- **base_path 必须是完整外部路径**。每个会话的 `StudioServer` 用 `base_path=<外部前缀>/s/<id>`(如 `/config-studio/s/<id>`)构造,否则前端 `studioUrl()` 拼出的 API 路径与 asset 重写前缀会缺宿主挂载前缀而 404。`StudioEmbedManager` 需知道自己的外部挂载前缀(经 `mount_embed_app(host_app, path)` 传入),**直接构造 `StudioServer(session=…, base_path=full)` 并 `manager.app.mount(f"/s/{id}", server.app)`**,不经 `mount_html_app`(它会用挂载相对路径当 base_path,丢前缀)。
- **manager 自己的 app 不设 catch-all**,故运行期追加的 `/s/<id>` mount 不会被吞;宿主再把 `manager.app` 挂在其 catch-all **之前**(HFT 侧负责)。
- **heartbeat 自动取消在挂载态本就不生效**:`StudioServer._check_heartbeat_timeout()` 只是可轮询方法,真正的 watcher loop 只存在于 `run_html_app`。manager **不为每会话跑 watcher** → 天然不自动取消;改由 manager 的 **idle-TTL 清扫**(读 `server.last_heartbeat_ts`,`/api/heartbeat` 仍在更新它)兜底回收被遗弃会话。
- **repeatable submit——绕开终态 409**:`routes.py` 的 `POST /api/mutations` 在 `session.outcome` 落定后返回 409(`_terminal_session_detail`)。`EditSession.submit()` 仅在**干净 `to_instance()`** 后置 `outcome="submitted"`(校验失败时**不置**,会话仍活)。embed 流程是"submit→宿主业务校验→可能失败→继续改",故宿主判失败后必须让会话回到非终态:manager 提供 **`reopen_session(id)`**(置 `session.outcome=None`),宿主 save 端点在业务校验失败时调它,mutations 随即恢复可用。宿主判成功则直接 `close_session(id)`。
- **前端 base_path 已全通**(`studioUrl()` 前缀全部 5 处 fetch),多会话**无需改 fetch 层**;只加 `sessionId` 注入 + postMessage(下）。
- **前端改动必须 `pnpm build` 并提交重生成的 `static/dist`**(CI 有 bundle drift gate,`git diff --exit-code`)。
- **发布同步**:`pyproject.toml` version 与 `src/pydantic_studio/__init__.py:__version__` 必须一致、且等于 `v*` tag(publish workflow 断言 `pyproject==__version__==tag`);`CHANGELOG.md` 的 `## <version>` 条目靠**约定**补(非机器强制)。本计划 `0.4.0 → 0.5.0`。

## 执行阶段

### 阶段 1 — `StudioEmbedManager`(后端)

- 新增 `src/pydantic_studio/renderers/html/embed.py`:`StudioEmbedManager`(`__init__(host_external_path, *, idle_ttl_seconds=900)`,持 `self.app`(一个 `FastAPI`/`Starlette`)+ `dict[str, tuple[StudioServer, Route]]`)与方法:
  - `create_session(*, tree, save_path=None, readonly_paths=()) -> str`:建 `EditSession`,构造 `StudioServer(session=…, base_path=f"{prefix}/s/{sid}")`,`self.app.mount(f"/s/{sid}", server.app)` 并记 route,返回 sid。sid 用 `secrets.token_hex`。
  - **`get_session(sid) -> EditSession`(或等价的 `tree` / `to_instance()` 访问器)**:宿主在**任意时刻**(包括会话仍活、`outcome is None` 时)读取当前编辑树/实例。⚠ 不要只暴露 `get_outcome(sid) -> EditOutcome | None`——`EditOutcome` **不携带 tree**,且活跃 embed 会话的 `outcome` 恒为 `None`(embed 模式下 submit 走宿主 save,不必然把会话置终态)。宿主 save 端点需要的是当前 tree 的 `to_instance()`,故必须有一个独立于终态的树访问器。`get_outcome` 仍可保留作只读状态查询。
  - `reopen_session(sid)`:`server.session.outcome=None`,让业务校验失败后 mutations 恢复可用。
  - `close_session(sid)`:**按存储的 `Route`/`Mount` 引用身份**从 `self.app.router.routes` 摘除(非按路径字符串匹配)+ 出 dict。
  - idle-TTL 清扫(按需 sweep 或后台任务,读 `server.last_heartbeat_ts`)。

  > **刻意选择**:让 `EditSession.submit()` 照常在干净校验后置终态 `outcome`,再由宿主判业务失败后调 `reopen_session` 复位——而非"embed 模式 submit 永不置终态"(spec §embed API 列的另一备选)。前者复用现有 `submit()` 路径不改、`get_outcome` 语义诚实;勿回退成后者。
- `mount_embed_app(host_app, path, *, idle_ttl_seconds=900) -> StudioEmbedManager`:`normalize_base_path(path)` 存为外部前缀,`host_app.mount(prefix, manager.app)`(镜像 `mount_html_app` 的 `getattr(host_app,"mount")` 守卫),返回 manager。
- 用 `EditSession(session=…)` 传入(避免 `_reject_session_parameter_conflicts` 冲突)。
- 导出:`src/pydantic_studio/renderers/html/__init__.py` + 顶层 `__init__.py` 加 `StudioEmbedManager` / `mount_embed_app`。
- 测试 `tests/unit/test_html_embed_manager.py`(沿用 `tests/unit/test_html_embedding.py` 的 `Starlette()` + `TestClient` 模式,`build_form_tree(_Schema)` 建树):两会话隔离(各自 `/s/<a>/api/tree` 独立,`window.__PYDANTIC_STUDIO__.basePath` 含完整前缀)、`close_session` 后该 `/s/<id>/` 404、`get_outcome`/`reopen_session`(submit 落定后 mutations 409 → reopen 后恢复 200)、idle-TTL 到期回收。

### 阶段 2 — 前端 sessionId + postMessage

- `frontend/src/api/base.ts`:`window.__PYDANTIC_STUDIO__` 类型加 `sessionId?: string`;`server.py:render_spa_index` 的注入 config 从 `{"basePath": …}` 扩为 `{"basePath": …, "sessionId": …}`(sessionId 由 `StudioServer` 新增可选构造参数携带,manager 建会话时传入)。
- `frontend/src/App.tsx`:`handleSave` 的 `if (response.ok)` 分支(**line 163** 附近,`setStatus("saved")` 处)与 `handleCancel` 的 `onSuccess`(**line 179** 附近,`setStatus("cancelled")` 处)各加 `window.parent.postMessage({ type: 'pydantic-studio:submitted' | 'pydantic-studio:cancelled', sessionId }, window.location.origin)`;`window.parent === window`(独立 run)时发给自身无害。仅 `response.ok===true` 才发 submitted。
- `pnpm build`(`cd frontend && pnpm build`)重生成并**提交** `src/pydantic_studio/renderers/html/static/dist/`。
- 测试:`test_html_embed_manager.py` 断言 mounted index 含 `"sessionId": "<id>"`;postMessage 若可抽纯函数则单测,否则靠 e2e/手动(跟随现有 e2e 边界)。

### 阶段 3 — 版本与变更日志

- `pyproject.toml` + `__init__.py:__version__`:`0.4.0 → 0.5.0`。
- `CHANGELOG.md` 加 `## 0.5.0`:多会话 embed manager、session-scoped base path、embed 模式无 heartbeat 自动取消 + idle-TTL、repeatable submit、postMessage 桥。

## 验证

- `uv run pytest -q`(全量,含新 `tests/unit/test_html_embed_manager.py`);`ruff check`;`pyright src/pydantic_studio`;`mkdocs build --strict`(若动 docs)。
- `cd frontend && pnpm build` 后 `git diff --exit-code src/pydantic_studio/renderers/html/static/dist`(须无 drift = 已提交最新 bundle)。
- 挂载 smoke:`TestClient` 起两会话,验证隔离 + 完整 base_path + close 后 404。

## 跨 repo 落地顺序

本计划**先行**(HFT 依赖它)。落地后发布:同步三处版本 → 打 `v0.5.0` tag 触发 publish workflow(公共 PyPI OIDC + piesource)。**发布留人工**(`.pypirc`/OIDC 凭据不由 agent 触碰)。私服 `pypi.piesource.cn/alpha/private` 自动同步(~30min);HFT 本机 editable 安装即时可用,CI/新环境等同步窗口。

## 完成后压缩规则

落地后保留本文件命名,压缩正文:保留设计偏差(base_path 完整前缀 / heartbeat 天然不触发 / repeatable-submit reopen 机制)、验证结论、发布同步规则和防回归测试点;删除执行阶段的实现细节清单。
