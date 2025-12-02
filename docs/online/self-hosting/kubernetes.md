# Kubernetes 部署

本指南介绍如何在 Kubernetes 集群上部署 Unifiles，实现高可用和自动扩展。

## 概述

Kubernetes 部署适合:
- 生产环境
- 需要高可用性
- 需要自动扩展
- 多租户隔离

## 前置要求

```bash
# Kubernetes 集群
kubectl version --client  # v1.24+

# Helm (推荐)
helm version  # v3.10+

# 存储类 (StorageClass)
kubectl get storageclass
```

## 使用 Helm 部署

### 1. 添加 Helm 仓库

```bash
helm repo add unifiles https://charts.unifiles.io
helm repo update
```

### 2. 创建命名空间

```bash
kubectl create namespace unifiles
```

### 3. 配置 values.yaml

```yaml
# values.yaml

# === 全局配置 ===
global:
  imageRegistry: ""
  imagePullSecrets: []
  storageClass: "standard"

# === API 服务 ===
api:
  replicaCount: 3
  
  image:
    repository: unifiles/api
    tag: "latest"
    pullPolicy: IfNotPresent
  
  resources:
    requests:
      cpu: 500m
      memory: 1Gi
    limits:
      cpu: 2000m
      memory: 4Gi
  
  autoscaling:
    enabled: true
    minReplicas: 3
    maxReplicas: 10
    targetCPUUtilization: 70
    targetMemoryUtilization: 80
  
  service:
    type: ClusterIP
    port: 8088
  
  ingress:
    enabled: true
    className: nginx
    annotations:
      cert-manager.io/cluster-issuer: letsencrypt-prod
      nginx.ingress.kubernetes.io/proxy-body-size: "100m"
    hosts:
      - host: api.unifiles.example.com
        paths:
          - path: /
            pathType: Prefix
    tls:
      - secretName: unifiles-tls
        hosts:
          - api.unifiles.example.com

# === Worker 服务 ===
workers:
  upload:
    replicaCount: 2
    resources:
      requests:
        cpu: 250m
        memory: 512Mi
      limits:
        cpu: 1000m
        memory: 2Gi
  
  extraction:
    replicaCount: 2
    resources:
      requests:
        cpu: 500m
        memory: 1Gi
      limits:
        cpu: 2000m
        memory: 4Gi

# === PostgreSQL ===
postgresql:
  enabled: true  # 设为 false 使用外部数据库
  
  auth:
    database: unifiles
    username: unifiles
    password: ""  # 留空自动生成
    existingSecret: ""
  
  primary:
    persistence:
      enabled: true
      size: 100Gi
      storageClass: ""
    
    resources:
      requests:
        cpu: 500m
        memory: 2Gi
      limits:
        cpu: 2000m
        memory: 8Gi
  
  # 高可用配置
  architecture: replication
  readReplicas:
    replicaCount: 2

# === Redis ===
redis:
  enabled: true
  
  auth:
    password: ""
    existingSecret: ""
  
  architecture: standalone  # 或 replication
  
  master:
    persistence:
      enabled: true
      size: 10Gi

# === MinIO ===
minio:
  enabled: true
  
  auth:
    rootUser: unifiles
    rootPassword: ""
    existingSecret: ""
  
  mode: distributed  # standalone 或 distributed
  statefulset:
    replicaCount: 4
  
  persistence:
    enabled: true
    size: 500Gi

# === 外部服务配置 (如果不使用内置服务) ===
externalDatabase:
  enabled: false
  host: ""
  port: 5432
  database: unifiles
  user: unifiles
  password: ""
  existingSecret: ""

externalRedis:
  enabled: false
  host: ""
  port: 6379
  password: ""
  existingSecret: ""

externalStorage:
  enabled: false
  type: s3  # s3, minio, oss
  endpoint: ""
  region: ""
  bucket: ""
  accessKey: ""
  secretKey: ""
  existingSecret: ""

# === 安全配置 ===
security:
  secretKey: ""  # 留空自动生成
  existingSecret: ""

# === 可观测性 ===
observability:
  metrics:
    enabled: true
    serviceMonitor:
      enabled: true
  
  tracing:
    enabled: false
    endpoint: ""
```

### 4. 部署

```bash
# 使用默认配置
helm install unifiles unifiles/unifiles -n unifiles

# 使用自定义配置
helm install unifiles unifiles/unifiles -n unifiles -f values.yaml

# 查看部署状态
kubectl get pods -n unifiles -w
```

### 5. 验证部署

```bash
# 检查 Pod 状态
kubectl get pods -n unifiles

# 检查服务
kubectl get svc -n unifiles

# 查看日志
kubectl logs -n unifiles -l app=unifiles-api -f

# 测试 API
kubectl port-forward -n unifiles svc/unifiles-api 8088:8088
curl http://localhost:8088/health
```

## 手动部署 (不使用 Helm)

### Namespace 和 ConfigMap

```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: unifiles

---
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: unifiles-config
  namespace: unifiles
data:
  LOG_LEVEL: "INFO"
  DEBUG: "false"
```

### Secrets

```yaml
# secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: unifiles-secrets
  namespace: unifiles
type: Opaque
stringData:
  PG_PASSWORD: "your_pg_password"
  REDIS_PASSWORD: "your_redis_password"
  MINIO_SECRET_KEY: "your_minio_secret"
  SECURITY_SECRET_KEY: "your_secret_key_at_least_32_chars"
```

### API Deployment

```yaml
# api-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: unifiles-api
  namespace: unifiles
spec:
  replicas: 3
  selector:
    matchLabels:
      app: unifiles-api
  template:
    metadata:
      labels:
        app: unifiles-api
    spec:
      containers:
        - name: api
          image: unifiles/api:latest
          ports:
            - containerPort: 8088
          env:
            - name: PG_HOST
              value: "unifiles-postgresql"
            - name: PG_PORT
              value: "5432"
            - name: PG_DATABASE
              value: "unifiles"
            - name: PG_USER
              value: "unifiles"
            - name: PG_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: unifiles-secrets
                  key: PG_PASSWORD
            - name: REDIS_HOST
              value: "unifiles-redis-master"
            - name: REDIS_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: unifiles-secrets
                  key: REDIS_PASSWORD
            - name: MINIO_ENDPOINT
              value: "unifiles-minio:9000"
            - name: MINIO_ACCESS_KEY
              value: "unifiles"
            - name: MINIO_SECRET_KEY
              valueFrom:
                secretKeyRef:
                  name: unifiles-secrets
                  key: MINIO_SECRET_KEY
            - name: SECURITY_SECRET_KEY
              valueFrom:
                secretKeyRef:
                  name: unifiles-secrets
                  key: SECURITY_SECRET_KEY
          resources:
            requests:
              cpu: 500m
              memory: 1Gi
            limits:
              cpu: 2000m
              memory: 4Gi
          livenessProbe:
            httpGet:
              path: /health
              port: 8088
            initialDelaySeconds: 30
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /health
              port: 8088
            initialDelaySeconds: 5
            periodSeconds: 5

---
# api-service.yaml
apiVersion: v1
kind: Service
metadata:
  name: unifiles-api
  namespace: unifiles
spec:
  selector:
    app: unifiles-api
  ports:
    - port: 8088
      targetPort: 8088
  type: ClusterIP
```

### Worker Deployment

```yaml
# worker-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: unifiles-worker-upload
  namespace: unifiles
spec:
  replicas: 2
  selector:
    matchLabels:
      app: unifiles-worker-upload
  template:
    metadata:
      labels:
        app: unifiles-worker-upload
    spec:
      containers:
        - name: worker
          image: unifiles/api:latest
          command: ["python", "-m", "unifiles.workers.upload_worker"]
          env:
            # ... 同 API 环境变量
          resources:
            requests:
              cpu: 250m
              memory: 512Mi
            limits:
              cpu: 1000m
              memory: 2Gi

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: unifiles-worker-extraction
  namespace: unifiles
spec:
  replicas: 2
  selector:
    matchLabels:
      app: unifiles-worker-extraction
  template:
    metadata:
      labels:
        app: unifiles-worker-extraction
    spec:
      containers:
        - name: worker
          image: unifiles/api:latest
          command: ["python", "-m", "unifiles.workers.extraction_worker"]
          env:
            # ... 同 API 环境变量
          resources:
            requests:
              cpu: 500m
              memory: 1Gi
            limits:
              cpu: 2000m
              memory: 4Gi
```

### Ingress

```yaml
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: unifiles-ingress
  namespace: unifiles
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/proxy-body-size: "100m"
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - api.unifiles.example.com
      secretName: unifiles-tls
  rules:
    - host: api.unifiles.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: unifiles-api
                port:
                  number: 8088
```

### HorizontalPodAutoscaler

```yaml
# hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: unifiles-api-hpa
  namespace: unifiles
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: unifiles-api
  minReplicas: 3
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
```

## 高可用配置

### Pod 反亲和性

```yaml
spec:
  affinity:
    podAntiAffinity:
      preferredDuringSchedulingIgnoredDuringExecution:
        - weight: 100
          podAffinityTerm:
            labelSelector:
              matchLabels:
                app: unifiles-api
            topologyKey: kubernetes.io/hostname
```

### Pod 中断预算

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: unifiles-api-pdb
  namespace: unifiles
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: unifiles-api
```

## 运维操作

### 升级

```bash
# Helm 升级
helm upgrade unifiles unifiles/unifiles -n unifiles -f values.yaml

# 手动升级 (滚动更新)
kubectl set image deployment/unifiles-api \
  api=unifiles/api:new-version -n unifiles
```

### 扩缩容

```bash
# 手动扩容
kubectl scale deployment unifiles-api --replicas=5 -n unifiles

# 查看 HPA 状态
kubectl get hpa -n unifiles
```

### 日志

```bash
# 查看 API 日志
kubectl logs -n unifiles -l app=unifiles-api -f

# 查看所有组件日志
kubectl logs -n unifiles -l app.kubernetes.io/instance=unifiles -f
```

## 下一步

- [配置说明](./configuration.md) - 详细配置选项
- [数据库设置](./database-setup.md) - PostgreSQL 高可用
- [可观测性](./observability.md) - Prometheus 和 Grafana
