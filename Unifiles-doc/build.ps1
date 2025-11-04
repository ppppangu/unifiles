# Windows PowerShell 构建脚本

$ErrorActionPreference = "Stop"

Write-Host "开始构建 Unifiles 静态站点..." -ForegroundColor Cyan

# 1. 构建 Next.js Landing Page
Write-Host "`n步骤 1/3: 构建 Next.js Landing Page..." -ForegroundColor Yellow
Set-Location pointer-landing-template
npm install
npm run build
Set-Location ..

# 2. 构建 MkDocs 文档
Write-Host "`n步骤 2/3: 构建 MkDocs 文档..." -ForegroundColor Yellow
uv sync
uv run mkdocs build

# 3. 合并静态文件
Write-Host "`n步骤 3/3: 合并静态文件..." -ForegroundColor Yellow
if (Test-Path "pointer-landing-template/out") {
    New-Item -ItemType Directory -Force -Path "pointer-landing-template/out/docs" | Out-Null
    Copy-Item -Path "site/*" -Destination "pointer-landing-template/out/docs/" -Recurse -Force
    Write-Host "`n✅ 构建完成！" -ForegroundColor Green
    Write-Host "📦 输出目录: pointer-landing-template/out/" -ForegroundColor Green
    Write-Host "   ├── / (Landing Page)" -ForegroundColor Green
    Write-Host "   └── /docs/ (文档)" -ForegroundColor Green
} else {
    Write-Host "`n❌ 错误：Next.js 构建失败，未找到 out 目录" -ForegroundColor Red
    exit 1
}
