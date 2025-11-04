# Unifiles 文档站点部署指南

本文档说明如何将 Unifiles 文档站点部署到 Cloudflare Pages。

## 项目结构

```
.
├── pointer-landing-template/   # Next.js Landing Page
│   ├── app/                     # Next.js 页面
│   ├── components/              # React 组件
│   └── out/                     # 构建输出（生成）
├── docs/                        # MkDocs 文档源文件
│   ├── index.md                 # 中文文档首页
│   └── index.en.md              # 英文文档首页
├── site/                        # MkDocs 构建输出（生成）
├── mkdocs.yml                   # MkDocs 配置
├── build.js                     # 构建脚本
└── package.json                 # 项目配置
```

## 路由结构

- `/` - Landing Page（中文）
- `/en/` - Landing Page（英文）
- `/docs/zh/` - 中文文档
- `/docs/en/` - 英文文档

## 本地开发

### 开发 Landing Page

```bash
cd pointer-landing-template
npm install
npm run dev
```

访问 http://localhost:3000

### 开发文档

```bash
uv sync
uv run mkdocs serve
```

访问 http://localhost:8000

## 构建

### 方法 1: 使用 Node.js 脚本（推荐）

```bash
npm install
npm run build
```

### 方法 2: 使用 Shell 脚本

**Linux/Mac:**
```bash
chmod +x build.sh
./build.sh
```

**Windows (PowerShell):**
```powershell
.\build.ps1
```

构建完成后，所有静态文件将位于 `pointer-landing-template/out/` 目录。

## 部署到 Cloudflare Pages

### 通过 Cloudflare Dashboard 部署

1. 登录 [Cloudflare Dashboard](https://dash.cloudflare.com/)
2. 进入 "Pages" 部分
3. 点击 "Create a project"
4. 连接你的 Git 仓库（GitHub/GitLab）
5. 配置构建设置：
   - **Framework preset**: None
   - **Build command**: `npm run build`
   - **Build output directory**: `pointer-landing-template/out`
   - **Root directory**: `/`
6. 环境变量（如需要）：
   ```
   NODE_VERSION=18
   PYTHON_VERSION=3.12
   ```
7. 点击 "Save and Deploy"

### 通过 Wrangler CLI 部署

```bash
# 安装 Wrangler
npm install -g wrangler

# 登录
wrangler login

# 部署
npm run build
cd pointer-landing-template/out
wrangler pages deploy . --project-name=unifiles-doc
```

## 自定义域名

1. 在 Cloudflare Pages 项目设置中
2. 进入 "Custom domains"
3. 添加你的域名
4. 按照提示配置 DNS

## 多语言支持

### Landing Page
- 使用客户端语言切换（右上角地球图标）
- 语言偏好保存在 localStorage

### 文档
- 使用 `mkdocs-static-i18n` 插件
- 支持中文（默认）和英文
- 每个 `.md` 文件对应一个 `.en.md` 文件

## 故障排除

### 构建失败

**问题**: Next.js 构建失败
```bash
cd pointer-landing-template
npm install
npm run build
```

**问题**: MkDocs 构建失败
```bash
uv sync
uv run mkdocs build
```

### 路径问题

确保 `next.config.mjs` 中配置了：
```javascript
{
  output: 'export',
  trailingSlash: true,
}
```

### 样式丢失

检查 `next.config.mjs` 中的 `images.unoptimized` 设置：
```javascript
{
  images: {
    unoptimized: true,
  },
}
```

## 性能优化

1. **启用 Cloudflare CDN** - 自动启用
2. **Brotli 压缩** - Cloudflare 自动处理
3. **HTTP/3** - 在 Cloudflare 设置中启用
4. **缓存规则** - 配置 Page Rules 优化缓存

## 监控

在 Cloudflare Pages 中查看：
- 部署历史
- 构建日志
- 分析数据
- 错误日志

## 支持

如有问题，请访问：
- [GitHub Issues](https://github.com/ppppangu/Unifiles-doc/issues)
- [Cloudflare Pages Docs](https://developers.cloudflare.com/pages/)
