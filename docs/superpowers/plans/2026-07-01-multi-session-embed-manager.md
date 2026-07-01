# 多会话 Embed Manager

> 设计规格见 HFT 侧 `HFT-Python/docs/specs/2026-07-01-serve-config-studio-embed-design.md`(跨 repo 设计的 studio 部分)。

## 结论

已实现并落地 `main` 前置分支 `embed-manager`:`StudioEmbedManager` / `mount_embed_app`
(`src/pydantic_studio/renderers/html/embed.py`),在已交付的**单会话** embed 基座
(`EditSession` / `mount_html_app` / base-path / `frontend/src/api/base.ts`)之上加了一层
**多会话**管理——一个挂载点按 session id 隔离并发编辑,宿主(如 hft serve)拥有生命周期。
纯通用库能力,不含任何 HFT 专属逻辑。

## 公共 API

```python
class StudioEmbedManager:
    def __init__(self, host_external_path: str, *, idle_ttl_seconds: float | None = 900) -> None: ...
    def create_session(self, *, tree, save_path=None, readonly_paths=()) -> str: ...  # 返回 session_id
    def get_session(self, session_id: str) -> EditSession: ...            # 树/实例访问器,任意时刻
    def get_outcome(self, session_id: str) -> EditOutcome | None: ...     # 只读状态查询
    def reopen_session(self, session_id: str) -> None: ...
    def close_session(self, session_id: str) -> None: ...
    def sweep_idle_sessions(self) -> None: ...
    @property
    def app(self): ...                                                   # FastAPI 子应用,供宿主 mount

def mount_embed_app(host_app, path: str, *, idle_ttl_seconds: float | None = 900) -> StudioEmbedManager: ...
```

`StudioServer` 新增可选 `session_id` 构造参数,随 `render_spa_index` 注入
`window.__PYDANTIC_STUDIO__ = {"basePath": ..., "sessionId": ...}`。

## 关键设计偏差与防回归(勿回退)

- **每会话 `StudioServer` 直接构造、带完整外部 `base_path`**(如
  `/config-studio/s/<id>`),不经 `mount_html_app`(它会用挂载相对路径当
  `base_path`,丢宿主前缀,导致前端 `studioUrl()` 拼出的 API/asset 路径 404)。
  `StudioEmbedManager` 记 `host_external_path`,`create_session` 里拼
  `f"{prefix}/s/{sid}"` 直传 `StudioServer(base_path=...)`。
- **manager 自己的 `self.app` 不设 catch-all**,故运行期 `create_session` 追加的
  `/s/<id>` mount 永远可达,不被任何先注册的路由吞掉;宿主把 `manager.app` 挂到
  自己 catch-all **之前**是宿主侧的责任。
- **heartbeat 自动取消在 embed 模式本就不生效**:`StudioServer._check_heartbeat_timeout()`
  只是可轮询方法,真正的 watcher loop 只存在于 `run_html_app`。manager 不为每会话
  跑 watcher,改用自己的 **`sweep_idle_sessions()`**(读 `server.last_heartbeat_ts`,
  `/api/heartbeat` 仍在更新它;`last_heartbeat_ts == 0.0` 即"还没收到心跳"不清扫,
  与单会话語义一致)兜底回收被遗弃会话。`idle_ttl_seconds=None` 整体禁用清扫。
- **`get_session` ≠ `get_outcome`**:`get_session(sid)` 返回活的 `EditSession`,任意时刻
  (含仍活跃、`outcome is None`)可用,是宿主读当前树 `to_instance()` 的入口;
  `get_outcome` 只读终态(`EditOutcome` 不带 tree)。
- **`reopen_session` 而非"embed 模式 submit 永不置终态"**:`EditSession.submit()`
  的既有行为**完全不改**——干净校验后仍置终态 `outcome="submitted"`。宿主业务校验
  失败后调 `reopen_session(sid)`(`session.outcome=None`)让 `/api/mutations` 摆脱
  409(`_terminal_session_detail`),会话回到可编辑态。宿主判成功则直接
  `close_session(sid)`,不 reopen。
- **`close_session` 按 `Route` 对象身份移除**(`self.app.router.routes.remove(route)`),
  非按路径字符串匹配——`create_session` 时把 `self.app.router.routes[-1]`(`mount()`
  刚 append 的那个)存起来配对 session id。
- 用 `EditSession(session=…)` 传入 `StudioServer`,避开 `_reject_session_parameter_conflicts`
  冲突检测。

## 前端

- `frontend/src/api/base.ts`:`window.__PYDANTIC_STUDIO__` 类型加 `sessionId?: string`
  (fetch 层零改动,`studioUrl()` 已经吃满 base_path)。
- `App.tsx`:`handleSave` 的 `response.ok===true` 分支与 `handleCancel` 的
  `onSuccess` 各触发 `window.parent.postMessage({type:'pydantic-studio:submitted'|'pydantic-studio:cancelled', sessionId}, window.location.origin)`;
  独立 run(`window.parent === window`)时发给自身无害。

## 验证结论

- `uv run pytest -q`:1329 passed(新增 `tests/unit/test_html_embed_manager.py` 11
  个用例:会话隔离、完整 base_path + `sessionId` 注入、`mount_embed_app` 挂载/护栏、
  `get_session` 活跃期可用、`close_session` 后 404、`get_outcome`/`reopen_session`
  终态-恢复往返、idle-TTL 清扫开/关、runtime-mount 不被 catch-all 吞、readonly_paths
  透传)。
- `ruff check .`、`pyright src/pydantic_studio`:均 0 error。
- `cd frontend && pnpm build` 后 `git diff --exit-code -- .../static/dist`:无 drift,
  已提交重生成 bundle。
- README.md / CLAUDE.md 的测试计数断言同步更新(默认 1318→1329,总数 1370→1381)。

## 发布同步规则

`pyproject.toml` version 与 `src/pydantic_studio/__init__.py:__version__` 已同步到
`0.5.0`(CHANGELOG.md 加 `## 0.5.0` 条目,`## 0.4.0` 历史条目原样保留)。**发布(打
`v0.5.0` tag 触发 publish workflow)留给人工**,agent 不碰 `.pypirc`/OIDC 凭据。
私服 `pypi.piesource.cn/alpha/private` 自动同步(~30min);HFT 本机 editable 安装
即时可用,CI/新环境等同步窗口。

## 跨 repo 落地顺序

本计划先行落地(HFT 侧依赖它),HFT 侧整合见 HFT-Python 的对应设计规格文档。
