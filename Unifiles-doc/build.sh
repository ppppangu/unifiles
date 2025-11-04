#!/bin/bash

set -e

echo "开始构建 Unifiles 静态站点..."

# 1. 构建 Next.js Landing Page
echo "步骤 1/3: 构建 Next.js Landing Page..."
cd pointer-landing-template
npm install
npm run build
cd ..

# 2. 构建 MkDocs 文档
echo "步骤 2/3: 构建 MkDocs 文档..."
uv sync
uv run mkdocs build

# 3. 合并静态文件
echo "步骤 3/3: 合并静态文件..."
# 将 MkDocs 构建输出移动到 Next.js 输出目录的 docs 子目录
if [ -d "pointer-landing-template/out" ]; then
    mkdir -p pointer-landing-template/out/docs
    cp -r site/* pointer-landing-template/out/docs/
    echo "✅ 构建完成！"
    echo "📦 输出目录: pointer-landing-template/out/"
    echo "   ├── / (Landing Page)"
    echo "   └── /docs/ (文档)"
else
    echo "❌ 错误：Next.js 构建失败，未找到 out 目录"
    exit 1
fi
