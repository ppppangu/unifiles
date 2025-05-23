# PostgreSQL 镜像构建与推送说明

## 目录结构
- Dockerfile：自定义镜像构建文件
- start.sh：容器启动脚本
- docker-compose.yaml：本地调试用
- sql-scripts/：初始化 SQL 脚本
- custom-config/：自定义配置

## 构建镜像
```bash
docker build -t <your-repo>/custom-postgres:latest .
```

## 推送镜像
```bash
docker push <your-repo>/custom-postgres:latest
```

## K8s 配置引用
在 StatefulSet/Deployment 的 image 字段填写：
```
<your-repo>/custom-postgres:latest
```

## 本地调试
```bash
docker-compose up -d
```
