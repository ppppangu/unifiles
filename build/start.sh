#!/bin/bash

# 检查网络是否存在，如果不存在则创建
if ! docker network ls | grep -q "outside_test"; then
  echo "网络 'outside_test' 不存在，正在创建..."
  docker network create outside_test
else
  echo "网络 'outside_test' 已存在，跳过创建步骤。"
fi

# 构建并启动容器
docker-compose build --no-cache
docker-compose up -d