# UniFiles 服务端模块化与 OpenAPI 多产物生成迁移

状态：实施中
目标架构：C+
适用范围：UniFiles monorepo

## 1. 目的

UniFiles 使用一份 OpenAPI contract 生成 FastAPI 协议层、Python 客户端核心和
TypeScript 客户端核心。迁移要同时表达两个正交维度：

1. 业务归属：system、files、documents、search 等。
2. 生命周期：generated 与 handwritten。

生成代码具有可整体删除、可整体重建、禁止手改、由 contract + generator +
config + template 决定的特殊语义。因此，本项目采用：

- 手写服务端代码 feature-first；
- 生成代码按独立 artifact 集中；
- 生成 router 暴露 factory；
- 各业务模块在本地静态绑定 router、实现 provider 和安全 provider；
- 应用入口显式 include_router；
- 不使用注册表、动态实现查找、resolve_api 或生成后按 tag 搬运。

## 2. 当前基线

基线提交：34df5a8。

当前已具备：

- OpenAPI Generator 7.24.0；
- 22 paths、33 operations；
- server、Python client、TypeScript client 三套可重复生成物；
- 18 个 Python 测试；
- 8 个 Node 测试；
- Python 3.11、3.12、3.13 CI 矩阵；
- Node 22、24 CI 矩阵；
- FastAPI Depends(provider) 实现注入。

当前仍未达到 C+：

- generated router 直接导入 unifiles_server.implementation.providers；
- generated security_api 直接导入 unifiles_server.auth；
- Base API 仍维护 subclasses，并非 ABC；
- app.py 仍通过 pkgutil/importlib 动态发现 router；
- 手写实现集中在 implementation/handlers.py；
- 生成目标分散在 apps/server 和两个手写 SDK package 内；
- contract 和 codegen 规则仍混放于 api/。

## 3. 最终决策

### 3.1 生成边界优先

generated 是构建产物边界，不是普通技术分层。每个 generator invocation 独占一个
artifact root：

    packages/generated/server-protocol-python/
    packages/generated/sdk-python/
    packages/generated/sdk-typescript/

每个根目录都必须可以独立删除、生成、检查、构建和测试。生成一个 target 不得改动
其他 target。

### 3.2 手写代码 feature-first

服务端手写代码按业务模块组织：

    apps/server/src/unifiles_server/modules/system/
    apps/server/src/unifiles_server/modules/files/
    apps/server/src/unifiles_server/modules/documents/
    ...

每个模块可包含：

- api.py：本地静态组装生成 router；
- implementation.py：协议入站适配；
- dependencies.py：对象构造和生命周期；
- authorization.py：模块授权；
- service.py 或 use_cases.py：业务规则；
- repository.py：模块数据访问；
- README.md：职责、边界和约束。

### 3.3 单向依赖

最终依赖方向：

    app
      -> modules/<feature>/api
           -> generated router factory
           -> module dependencies
                -> implementation
                     -> service
                     -> generated Base API + DTO

禁止：

    packages/generated/** -> unifiles_server

### 3.4 Generated models 保持集中

OpenAPI Schema Object 没有标准 tag ownership。一个 schema 可以被多个 operation
共享，因此生成模型继续集中在 protocol/client target 内。复杂业务可在模块内部定义
领域对象；生成 Pydantic model 只作为传输 DTO。

### 3.5 CLI 是手写产品应用

当前 TypeScript CLI 是手写产品 CLI，包含 profile、凭据文件、输出格式和错误体验。
它不作为 OpenAPI 的机械生成目标。最终移动到 apps/cli，并依赖公开 TypeScript SDK。
本次目录迁移不改写 CLI 语言或用户行为。

## 4. 最终目录

    repo/
    ├── contracts/
    │   └── openapi/
    │       ├── unifiles.yaml
    │       ├── overlays/
    │       └── README.md
    ├── codegen/
    │   ├── VERSION
    │   ├── manifest.yaml
    │   ├── configs/
    │   │   ├── server-protocol-python.yaml
    │   │   ├── sdk-python.yaml
    │   │   └── sdk-typescript.yaml
    │   ├── templates/
    │   │   └── python-fastapi/
    │   ├── scripts/
    │   │   ├── codegen.py
    │   │   ├── validate_contract.py
    │   │   └── check_generated_imports.py
    │   └── README.md
    ├── apps/
    │   ├── server/
    │   │   ├── pyproject.toml
    │   │   ├── src/unifiles_server/
    │   │   │   ├── modules/
    │   │   │   ├── shared/
    │   │   │   └── app.py
    │   │   └── tests/
    │   └── cli/
    ├── packages/
    │   ├── generated/
    │   │   ├── server-protocol-python/
    │   │   ├── sdk-python/
    │   │   └── sdk-typescript/
    │   ├── python/
    │   └── typescript/
    ├── migration/
    │   └── operation-ownership.csv
    ├── .codegen-work/
    └── dist/

packages/python 和 packages/typescript 保留公开 SDK 的手写体验层；对应 generated target
提供协议客户端核心。这样重试、错误映射、轮询和资源 API 不会因重新生成丢失。

## 5. Router factory

生成 router 不导入应用 provider。每个生成 API 模块暴露 create_router：

    ImplementationProvider = Callable[..., BaseSystemApi]
    BearerAuthProvider = Callable[..., TokenModel]

    def create_router(
        get_implementation: ImplementationProvider,
        get_bearer_auth: BearerAuthProvider,
    ) -> APIRouter:
        router = APIRouter()

        @router.get("/v1/health/details")
        async def get_health_details(
            implementation: Annotated[
                BaseSystemApi,
                Depends(get_implementation),
            ],
            token: Annotated[
                TokenModel,
                Security(get_bearer_auth),
            ],
        ) -> HealthDetailsResponse:
            return await implementation.get_health_details()

        return router

公开 operation 不声明安全依赖。受保护 operation 使用由应用传入的安全 provider。
因此，router factory 必须同时消除实现 provider 和 security_api 的反向应用依赖。

模块本地组装：

    from unifiles_server_protocol.apis.system_api import create_router

    from ...shared.auth import get_bearer_principal
    from .dependencies import get_system_api_implementation

    router = create_router(
        get_system_api_implementation,
        get_bearer_principal,
    )

这仍然使用 FastAPI 完整依赖树。Provider 可以继续声明 Depends 子依赖。

## 6. Base API

Base API 使用 ABC 和 abstractmethod，不维护 subclass registry：

    class BaseSystemApi(ABC):
        @abstractmethod
        async def get_health_details(self) -> HealthDetailsResponse:
            raise NotImplementedError

收益：

- 漏实现的方法在对象构造时失败；
- 无自动发现；
- 无字符串或字典实现映射；
- 生成协议包不需要知道应用类。

## 7. 模块职责

### api.py

只组装生成 router、实现 provider 和安全 provider，不重复声明 path、参数或响应。

### implementation.py

负责 generated DTO、HTTP 参数和内部对象的转换，以及调用 service/use case。它是协议
适配器，不是整个业务层。

### dependencies.py

负责对象构造和生命周期。无状态轻量实现可按请求创建；数据库 session 按请求管理；
HTTP client、连接池、模型和对象存储 client 由应用 lifespan 管理。

### service.py / use_cases.py

负责业务规则，不依赖 FastAPI request/response。简单模块可暂时保持轻量，但不得把
不断增长的业务永久塞入 implementation.py。

### shared/

只存确实跨模块且语义稳定的基础设施：

- auth.py；
- database.py；
- errors.py；
- settings.py；
- responses.py。

shared 不是杂物箱。模块专属权限和规则留在模块内部。

## 8. OpenAPI ownership

每个 operation 必须：

- 有且仅有一个业务 tag；
- operationId 全局唯一并使用 lowerCamelCase；
- tag 属于允许列表；
- tag 映射到一个 feature module；
- 明确声明认证要求。

迁移期间由 migration/operation-ownership.csv 固化：

    operation_id,path,method,tag,module,base_api,implementation,provider

生成 models 不按 tag 搬运。

## 9. Codegen manifest

manifest 是唯一 target 清单：

    version: 1
    spec: contracts/openapi/unifiles.yaml
    generatedRoot: packages/generated
    workRoot: .codegen-work

    tool:
      command:
        - ./node_modules/.bin/openapi-generator-cli
      versionFile: codegen/VERSION

    targets:
      server-protocol-python:
        generatorName: python-fastapi
        config: codegen/configs/server-protocol-python.yaml
        templateDir: codegen/templates/python-fastapi
        outputDir: packages/generated/server-protocol-python
      sdk-python:
        generatorName: python
        config: codegen/configs/sdk-python.yaml
        outputDir: packages/generated/sdk-python
      sdk-typescript:
        generatorName: typescript-fetch
        config: codegen/configs/sdk-typescript.yaml
        outputDir: packages/generated/sdk-typescript

不依赖 batch 命令完成安全替换；项目 wrapper 负责 target 选择、后处理、校验和原子替换。

## 10. 安全生成

每次生成：

1. 验证 manifest target；
2. 验证输出位于 packages/generated 的登记叶子目录；
3. 验证 Generator 精确版本；
4. 生成到 .codegen-work 下的唯一临时目录；
5. 执行 target 专属后处理；
6. 检查 required paths；
7. 写入确定性 .codegen-target.json；
8. 执行 import/build/smoke hook；
9. 使用备份和回滚语义替换正式目录；
10. 清理临时目录。

禁止任意 --output 参数。删除范围只能来自 manifest。

.codegen-target.json 至少记录：

    {
      "target": "server-protocol-python",
      "generatorVersion": "7.24.0",
      "specSha256": "...",
      "configSha256": "...",
      "templateSha256": "..."
    }

不写生成时间，避免无意义 diff。

## 11. Generated 与 dist

packages/generated 保存参与编译和测试的源码投影。dist 只保存 wheel、sdist、npm tgz
和 CLI 可执行发布物。两者不能混用。

## 12. 迁移阶段与提交

### 提交 1：Codegen 基线与版本固定

- 固定 Generator 版本；
- 验证三套生成物可重复；
- 增加 ownership inventory；
- 增加 operation/tag/route 唯一性约束；
- 保存本文档。

### 提交 2：Contract、codegen 与 server protocol artifact

- 移动 contract 到 contracts/openapi；
- 移动 config/template 到 codegen；
- 建立 manifest 和安全 codegen wrapper；
- 迁移 server protocol；
- 接入 uv workspace；
- 删除 apps/server/generated；
- 保持服务行为不变。

### 提交 3：system、files 试点

- 建立 feature-first 目录；
- 移动 implementation/provider；
- 必要时保留静态兼容 re-export；
- 不改变 HTTP 行为。

### 提交 4：其余模块与 shared

- 迁移 api_keys、documents、extractions、knowledge_bases、search、usage、webhooks；
- 移动共享基础设施；
- 中央 handlers/providers 缩减为薄静态兼容导出；
- auth 移入 shared 后保留顶层静态兼容导出；
- 在 router factory 切换前不删除 generated 仍在导入的兼容入口。

### 提交 5：Router factory 与单向依赖

- 定制 api.mustache；
- 定制 Base API template；
- 注入实现和安全 provider；
- 每个模块增加 api.py；
- app 显式 include_router；
- 删除动态扫描、中央 providers/handlers 及顶层 auth 等所有兼容层；
- 增加 generated import 边界测试。

### 提交 6：SDK target 与 CLI 边界

- 迁移 sdk-python 和 sdk-typescript；
- 公开 SDK 手写层依赖对应 generated core；
- 移动手写 CLI 到 apps/cli；
- 保持 CLI 语言和行为；
- 分别 build/pack/smoke test。

### 提交 7：CI、发布与清理

- codegen check all；
- contract validation；
- generated import AST 检查；
- route/operation 唯一性；
- wheel/npm/CLI 构建；
- 删除旧路径和旧脚本；
- 更新开发、发布和回滚文档。

每次提交前必须由独立子代理审查：

- 是否偏离 C+；
- 是否引入动态查找或注册表；
- generated 是否反向导入 app；
- 删除边界是否安全；
- 本阶段是否混入下一阶段行为变更；
- 测试与漂移检查是否完整。

## 13. CI 强制项

CI 至少包含：

- OpenAPI 规范校验；
- duplicate YAML key 检查；
- operationId 唯一；
- 每个 operation 一个业务 tag；
- security scheme 约束；
- operation ownership inventory 漂移检查；
- codegen check all；
- generated 不导入 unifiles_server；
- 手写代码不位于 generated root；
- app import smoke；
- router factory 可创建；
- method + path 无重复；
- app OpenAPI operationId 无重复；
- Python 测试、ruff、mypy；
- TypeScript build、typecheck、test；
- Python wheel 与 npm pack。

## 14. 回滚

每阶段独立提交并保持可运行。失败只回滚当前阶段，不添加新的混合机制。

- artifact 路径失败：恢复上一提交的旧 output root；
- 模块拆分失败：利用静态兼容导出单模块回退；
- router factory 失败：恢复上一提交，不恢复 resolve_api；
- SDK target 失败：恢复旧 generated core 路径，不改公开 SDK API。

## 15. 日常工作流

新增 operation：

1. 修改 contract；
2. 指定唯一 operationId 和业务 tag；
3. validate；
4. generate all；
5. 在对应模块实现 Base API；
6. 增加 service 和测试；
7. check all；
8. 提交 contract、generated、handwritten。

新增模块不需要注册表、生成文件搬运或动态 import；只需建立模块目录、生成协议、创建
本地 api.py 并在 app.py 显式挂载。

## 16. 最终验收

目录：

- 无 apps/server/generated；
- 无含混的全局 generated/src；
- 每个 target 有独立 artifact root；
- generated 与 dist 分离。

生成：

- 精确版本固定；
- generate all 可从空目录重建；
- check all 在干净仓库通过；
- 单目标生成不影响其他目标；
- 删除 operation 不残留旧文件；
- generated 无手写文件。

服务端：

- 每个业务 tag 有 feature module；
- generated 不导入 unifiles_server；
- app 显式挂载 router；
- 无注册表、resolve_api、动态 router 发现；
- Base API 为抽象接口；
- 认证和授权行为保持；
- 无重复 route 和 operationId。

分发：

- server protocol 可单独构建；
- Python SDK 可构建 wheel；
- TypeScript SDK 可 build/pack；
- CLI 依赖 SDK，不复制 HTTP 协议；
- 发布物仅进入 dist 或制品仓库。

## 17. 非目标

本迁移不采用 per-tag generated 物理拆分，不维护 tag-to-directory codegen 映射，不通过
custom generator 或生成后搬运换取生成源码共址。只有当模块独立部署、独立 contract、
独立版本和独立兼容策略时，才考虑拆分服务与 contract。
