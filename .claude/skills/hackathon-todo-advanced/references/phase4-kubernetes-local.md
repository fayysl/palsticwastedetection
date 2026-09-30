# Phase 4: Local Kubernetes Deployment (Minikube)

## Overview

Phase 4 deploys your AI chatbot to a local Kubernetes cluster using:
- **Docker**: Containerize frontend and backend
- **Minikube**: Local Kubernetes cluster
- **Helm**: Package manager for Kubernetes
- **kubectl-ai & kagent**: AI-powered cluster management

## Prerequisites

- Docker Desktop installed
- Minikube installed
- kubectl installed
- Helm installed
- kubectl-ai installed (optional but recommended)

## Step 1: Containerization

### 1.1 Backend Dockerfile

```dockerfile
# backend/Dockerfile
FROM python:3.13-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port
EXPOSE 8000

# Run FastAPI
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 1.2 Frontend Dockerfile

```dockerfile
# frontend/Dockerfile
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm ci

# Build application
COPY . .
RUN npm run build

# Production image
FROM node:20-alpine

WORKDIR /app

COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/public ./public

EXPOSE 3000

CMD ["npm", "start"]
```

### 1.3 Build and Test Locally

```bash
# Build images
docker build -t todo-backend:latest ./backend
docker build -t todo-frontend:latest ./frontend

# Test backend
docker run -p 8000:8000 \
  -e DATABASE_URL=$DATABASE_URL \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  todo-backend:latest

# Test frontend
docker run -p 3000:3000 \
  -e NEXT_PUBLIC_API_URL=http://localhost:8000 \
  todo-frontend:latest
```

## Step 2: Minikube Setup

### 2.1 Start Minikube

```bash
# Start with sufficient resources
minikube start --cpus=4 --memory=8192 --driver=docker

# Enable addons
minikube addons enable ingress
minikube addons enable metrics-server

# Verify cluster
kubectl cluster-info
kubectl get nodes
```

### 2.2 Load Docker Images

```bash
# Load images into Minikube
minikube image load todo-backend:latest
minikube image load todo-frontend:latest

# Verify images loaded
minikube image ls | grep todo
```

## Step 3: Helm Chart Creation

### 3.1 Initialize Helm Chart

```bash
# Create chart structure
helm create hackathon-todo

# Directory structure:
# hackathon-todo/
# ├── Chart.yaml
# ├── values.yaml
# └── templates/
#     ├── backend-deployment.yaml
#     ├── backend-service.yaml
#     ├── frontend-deployment.yaml
#     ├── frontend-service.yaml
#     ├── secrets.yaml
#     └── ingress.yaml
```

### 3.2 Chart.yaml

```yaml
# hackathon-todo/Chart.yaml
apiVersion: v2
name: hackathon-todo
description: AI-powered todo chatbot
type: application
version: 1.0.0
appVersion: "1.0"
```

### 3.3 Values.yaml

```yaml
# hackathon-todo/values.yaml
backend:
  image:
    repository: todo-backend
    tag: latest
    pullPolicy: Never  # Use local images
  replicas: 2
  port: 8000
  env:
    DATABASE_URL: "postgresql://user:pass@neon.tech/db"
    OPENAI_API_KEY: "sk-..."
    BETTER_AUTH_SECRET: "your-secret"

frontend:
  image:
    repository: todo-frontend
    tag: latest
    pullPolicy: Never
  replicas: 2
  port: 3000
  env:
    NEXT_PUBLIC_API_URL: "http://backend-service:8000"
    NEXT_PUBLIC_OPENAI_DOMAIN_KEY: "your-domain-key"

ingress:
  enabled: true
  host: todo.local
```

### 3.4 Backend Deployment Template

```yaml
# hackathon-todo/templates/backend-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Chart.Name }}-backend
  labels:
    app: {{ .Chart.Name }}
    component: backend
spec:
  replicas: {{ .Values.backend.replicas }}
  selector:
    matchLabels:
      app: {{ .Chart.Name }}
      component: backend
  template:
    metadata:
      labels:
        app: {{ .Chart.Name }}
        component: backend
    spec:
      containers:
      - name: backend
        image: "{{ .Values.backend.image.repository }}:{{ .Values.backend.image.tag }}"
        imagePullPolicy: {{ .Values.backend.image.pullPolicy }}
        ports:
        - containerPort: {{ .Values.backend.port }}
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: {{ .Chart.Name }}-secrets
              key: database-url
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: {{ .Chart.Name }}-secrets
              key: openai-api-key
        - name: BETTER_AUTH_SECRET
          valueFrom:
            secretKeyRef:
              name: {{ .Chart.Name }}-secrets
              key: auth-secret
        livenessProbe:
          httpGet:
            path: /health
            port: {{ .Values.backend.port }}
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: {{ .Values.backend.port }}
          initialDelaySeconds: 5
          periodSeconds: 5
```

### 3.5 Backend Service Template

```yaml
# hackathon-todo/templates/backend-service.yaml
apiVersion: v1
kind: Service
metadata:
  name: backend-service
  labels:
    app: {{ .Chart.Name }}
    component: backend
spec:
  type: ClusterIP
  ports:
  - port: {{ .Values.backend.port }}
    targetPort: {{ .Values.backend.port }}
    protocol: TCP
  selector:
    app: {{ .Chart.Name }}
    component: backend
```

### 3.6 Secrets Template

```yaml
# hackathon-todo/templates/secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: {{ .Chart.Name }}-secrets
type: Opaque
stringData:
  database-url: {{ .Values.backend.env.DATABASE_URL }}
  openai-api-key: {{ .Values.backend.env.OPENAI_API_KEY }}
  auth-secret: {{ .Values.backend.env.BETTER_AUTH_SECRET }}
```

## Step 4: Deploy to Minikube

### 4.1 Install with Helm

```bash
# Install chart
helm install hackathon-todo ./hackathon-todo

# Verify deployment
kubectl get pods
kubectl get services
kubectl get deployments

# Check logs
kubectl logs -l component=backend
kubectl logs -l component=frontend
```

### 4.2 Access Application

```bash
# Get Minikube IP
minikube ip
# Example output: 192.168.49.2

# Add to /etc/hosts
echo "$(minikube ip) todo.local" | sudo tee -a /etc/hosts

# Access application
curl http://todo.local
# or open in browser: http://todo.local
```

### 4.3 Port Forwarding (Alternative)

```bash
# Forward backend port
kubectl port-forward service/backend-service 8000:8000

# Forward frontend port
kubectl port-forward service/frontend-service 3000:3000

# Access: http://localhost:3000
```

## Step 5: kubectl-ai & kagent Integration

### 5.1 Install kubectl-ai

```bash
# Install kubectl-ai
brew install kubectl-ai
# or
curl -sSL https://raw.githubusercontent.com/sozercan/kubectl-ai/main/install.sh | bash

# Configure
kubectl ai setup --api-key $OPENAI_API_KEY
```

### 5.2 Use kubectl-ai

```bash
# Deploy with natural language
kubectl ai "deploy the todo frontend with 2 replicas"

# Scale application
kubectl ai "scale the backend to handle more load"

# Check pod health
kubectl ai "check why the pods are failing"

# Get resource usage
kubectl ai "show me which pods are using the most memory"

# Debug issues
kubectl ai "why is the frontend service not accessible"
```

### 5.3 Install kagent (Optional)

```bash
# Install kagent
go install github.com/kubefirst/kagent@latest

# Use kagent
kagent "analyze the cluster health"
kagent "optimize resource allocation"
kagent "find potential security issues"
```

## Step 6: Monitoring & Debugging

### 6.1 View Logs

```bash
# Stream backend logs
kubectl logs -f deployment/hackathon-todo-backend

# View last 100 lines
kubectl logs deployment/hackathon-todo-frontend --tail=100

# Follow logs from multiple pods
kubectl logs -l component=backend --all-containers=true -f
```

### 6.2 Debug Pods

```bash
# Describe pod to see events
kubectl describe pod <pod-name>

# Execute commands in pod
kubectl exec -it <pod-name> -- /bin/sh

# Check environment variables
kubectl exec <pod-name> -- env | grep DATABASE
```

### 6.3 Minikube Dashboard

```bash
# Launch Kubernetes dashboard
minikube dashboard

# Opens browser with visual cluster view:
# - Pod status
# - Resource usage
# - Logs viewer
# - Events
```

## Step 7: Testing Checklist

- [ ] Backend pods running and healthy
- [ ] Frontend pods running and healthy
- [ ] Services exposing correct ports
- [ ] Secrets properly mounted
- [ ] Database connectivity working
- [ ] MCP server accessible from backend
- [ ] Frontend can reach backend API
- [ ] Chat functionality working end-to-end
- [ ] Multiple replicas load balancing

## Common Issues & Solutions

### Issue: ImagePullBackOff
**Solution**: Images not loaded to Minikube
```bash
minikube image load todo-backend:latest
minikube image load todo-frontend:latest
```

### Issue: CrashLoopBackOff
**Solution**: Check pod logs for application errors
```bash
kubectl logs <pod-name>
kubectl describe pod <pod-name>
```

### Issue: Service not accessible
**Solution**: Verify service selector matches pod labels
```bash
kubectl get pods --show-labels
kubectl get service backend-service -o yaml
```

### Issue: Environment variables not set
**Solution**: Check secrets are created and mounted
```bash
kubectl get secrets
kubectl describe secret hackathon-todo-secrets
kubectl exec <pod-name> -- env
```

## Cleanup

```bash
# Uninstall Helm release
helm uninstall hackathon-todo

# Delete Minikube cluster
minikube delete

# Remove /etc/hosts entry
sudo sed -i '/todo.local/d' /etc/hosts
```

## Next Steps

1. Verify local Kubernetes deployment working
2. Document deployment process
3. Prepare for Phase 5: Cloud deployment
4. Consider Dapr integration for Phase 5
