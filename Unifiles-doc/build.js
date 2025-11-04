#!/usr/bin/env node

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

function exec(command, cwd = process.cwd()) {
  console.log(`> ${command}`);
  execSync(command, {
    cwd,
    stdio: 'inherit',
    shell: true
  });
}

function copyDir(src, dest) {
  if (!fs.existsSync(dest)) {
    fs.mkdirSync(dest, { recursive: true });
  }

  const entries = fs.readdirSync(src, { withFileTypes: true });

  for (const entry of entries) {
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);

    if (entry.isDirectory()) {
      copyDir(srcPath, destPath);
    } else {
      fs.copyFileSync(srcPath, destPath);
    }
  }
}

console.log('🚀 开始构建 Unifiles 静态站点...\n');

try {
  // 步骤 1: 构建 Next.js Landing Page
  console.log('📦 步骤 1/3: 构建 Next.js Landing Page...');
  exec('npm install', 'pointer-landing-template');
  exec('npm run build', 'pointer-landing-template');
  console.log('✅ Next.js 构建完成\n');

  // 步骤 2: 构建 MkDocs 文档
  console.log('📚 步骤 2/3: 构建 MkDocs 文档...');
  exec('uv sync');
  exec('uv run mkdocs build');
  console.log('✅ MkDocs 构建完成\n');

  // 步骤 3: 合并静态文件
  console.log('🔗 步骤 3/3: 合并静态文件...');
  const outDir = path.join(__dirname, 'pointer-landing-template', 'out');
  const docsOutDir = path.join(outDir, 'docs');
  const siteDir = path.join(__dirname, 'site');

  if (!fs.existsSync(outDir)) {
    throw new Error('Next.js 构建失败，未找到 out 目录');
  }

  if (fs.existsSync(docsOutDir)) {
    fs.rmSync(docsOutDir, { recursive: true });
  }

  copyDir(siteDir, docsOutDir);
  console.log('✅ 文件合并完成\n');

  console.log('🎉 构建成功！');
  console.log('📦 输出目录: pointer-landing-template/out/');
  console.log('   ├── / (Landing Page)');
  console.log('   └── /docs/ (文档)');

} catch (error) {
  console.error('❌ 构建失败:', error.message);
  process.exit(1);
}
