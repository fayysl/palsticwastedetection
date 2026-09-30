# Phase 5: Cloud Deployment with Dapr & Kafka

## Overview

Phase 5 deploys to production cloud infrastructure with:
- **DigitalOcean Kubernetes (DOKS)** or **Google GKE** or **Azure AKS**
- **Dapr**: Distributed application runtime
- **Kafka**: Event-driven architecture (Redpanda Cloud or self-hosted)
- **Advanced Features**: Recurring tasks, due dates, reminders

## Architecture

```
┌────────────────────────────────────────────────────────────┐
│  CLOUD KUBERNETES CLUSTER (DOKS/GKE/AKS)                   │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────┐  │
│  │ Frontend Pod│  │ Backend Pod │  │ Notification Pod │  │
│  │ +Dapr       │  │ +Dapr       │  │ +Dapr            │  │
│  └──────┬──────┘  └──────┬──────┘  └────────┬─────────┘  │
│         │                 │                   │             │
│         └─────────────────┼───────────────────┘             │
│                           ▼                                 │
│              ┌─────────────────────────┐                    │
│              │   Dapr Components       │                    │
│              │ - Pub/Sub (Kafka)       │                    │
│              │ - State Store (Postgres)│                    │
│              │ - Secrets               │                    │
│              │ - Jobs API              │                    │
│              └─────────────────────────┘                    │
└────────────────────────────────────────────────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────┐
        │  External Services               │
        │  - Redpanda Cloud (Kafka)        │
        │  - Neon DB (PostgreSQL)          │
        │  - OpenAI API                    │
        └──────────────────────────────────┘
```

## Step 1: Cloud Provider Setup

### Option A: DigitalOcean (Recommended - $200 credit)

```bash
# Install doctl
brew install doctl
# or: wget -qO- https://github.com/digitalocean/doctl/releases/latest/download/doctl-linux-amd64.tar.gz | tar xz

# Authenticate
doctl auth init

# Create Kubernetes cluster
doctl kubernetes cluster create hackathon-todo \
  --region nyc1 \
  --version latest \
  --node-pool "name=workers;size=s-2vcpu-4gb;count=3"

# Get kubeconfig
doctl kubernetes cluster kubeconfig save hackathon-todo

# Verify connection
kubectl get nodes
```

### Option B: Google Cloud (GKE - $300 credit)

```bash
# Install gcloud CLI
curl https://sdk.cloud.google.com | bash

# Authenticate
gcloud init
gcloud auth login

# Create cluster
gcloud container clusters create hackathon-todo \
  --zone us-central1-a \
  --num-nodes 3 \
  --machine-type n1-standard-2

# Get credentials
gcloud container clusters get-credentials hackathon-todo --zone us-central1-a

# Verify
kubectl get nodes
```

### Option C: Azure (AKS - $200 credit)

```bash
# Install Azure CLI
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Login
az login

# Create resource group
az group create --name hackathon-todo-rg --location eastus

# Create cluster
az aks create \
  --resource-group hackathon-todo-rg \
  --name hackathon-todo \
  --node-count 3 \
  --enable-addons monitoring \
  --generate-ssh-keys

# Get credentials
az aks get-credentials --resource-group hackathon-todo-rg --name hackathon-todo

# Verify
kubectl get nodes
```

## Step 2: Dapr Installation

### 2.1 Install Dapr CLI

```bash
# Install Dapr CLI
curl -fsSL https://raw.githubusercontent.com/dapr/cli/master/install/install.sh | bash

# Verify installation
dapr version
```

### 2.2 Initialize Dapr on Kubernetes

```bash
# Install Dapr on cluster
dapr init -k

# Verify Dapr installation
dapr status -k

# Expected output:
# - dapr-operator
# - dapr-sidecar-injector
# - dapr-sentry
# - dapr-placement-server
```

## Step 3: Kafka Setup

### Option A: Redpanda Cloud (Recommended - Free Tier)

```bash
# Sign up: https://redpanda.com/cloud
# Create Serverless cluster

# Note credentials:
KAFKA_BROKERS="your-cluster.cloud.redpanda.com:9092"
KAFKA_USERNAME="your-username"
KAFKA_PASSWORD="your-password"

# Create topics
rpk topic create task-events --brokers $KAFKA_BROKERS \
  --user $KAFKA_USERNAME --password $KAFKA_PASSWORD
  
rpk topic create reminders --brokers $KAFKA_BROKERS \
  --user $KAFKA_USERNAME --password $KAFKA_PASSWORD
```

### Option B: Self-Hosted Kafka (Strimzi)

```bash
# Install Strimzi operator
kubectl create namespace kafka
kubectl apply -f 'https://strimzi.io/install/latest?namespace=kafka' -n kafka

# Create Kafka cluster
cat <<EOF | kubectl apply -f -
apiVersion: kafka.strimzi.io/v1beta2
kind: Kafka
metadata:
  name: taskflow-kafka
  namespace: kafka
spec:
  kafka:
    replicas: 3
    listeners:
      - name: plain
        port: 9092
        type: internal
        tls: false
    storage:
      type: persistent-claim
      size: 10Gi
  zookeeper:
    replicas: 3
    storage:
      type: persistent-claim
      size: 10Gi
EOF

# Create topics
cat <<EOF | kubectl apply -f -
apiVersion: kafka.strimzi.io/v1beta2
kind: KafkaTopic
metadata:
  name: task-events
  namespace: kafka
  labels:
    strimzi.io/cluster: taskflow-kafka
spec:
  partitions: 3
  replicas: 2
---
apiVersion: kafka.strimzi.io/v1beta2
kind: KafkaTopic
metadata:
  name: reminders
  namespace: kafka
  labels:
    strimzi.io/cluster: taskflow-kafka
spec:
  partitions: 3
  replicas: 2
EOF
```

## Step 4: Dapr Components Configuration

### 4.1 Pub/Sub Component (Kafka)

```yaml
# dapr-components/pubsub.yaml
apiVersion: dapr.io/v1alpha1
kind: Component
metadata:
  name: kafka-pubsub
  namespace: default
spec:
  type: pubsub.kafka
  version: v1
  metadata:
  - name: brokers
    value: "your-cluster.cloud.redpanda.com:9092"
  - name: consumerGroup
    value: "todo-service"
  - name: authType
    value: "password"
  - name: saslUsername
    value: "your-username"
  - name: saslPassword
    secretKeyRef:
      name: kafka-secrets
      key: password
```

### 4.2 State Store Component (PostgreSQL)

```yaml
# dapr-components/statestore.yaml
apiVersion: dapr.io/v1alpha1
kind: Component
metadata:
  name: statestore
  namespace: default
spec:
  type: state.postgresql
  version: v1
  metadata:
  - name: connectionString
    secretKeyRef:
      name: db-secrets
      key: connection-string
  - name: tableName
    value: "dapr_state"
```

### 4.3 Secrets Store Component

```yaml
# dapr-components/secrets.yaml
apiVersion: dapr.io/v1alpha1
kind: Component
metadata:
  name: kubernetes-secrets
  namespace: default
spec:
  type: secretstores.kubernetes
  version: v1
```

### 4.4 Apply Dapr Components

```bash
# Create secrets first
kubectl create secret generic kafka-secrets \
  --from-literal=password=$KAFKA_PASSWORD

kubectl create secret generic db-secrets \
  --from-literal=connection-string=$DATABASE_URL

# Apply Dapr components
kubectl apply -f dapr-components/
```

## Step 5: Update Application for Dapr

### 5.1 Backend with Dapr Pub/Sub

```python
# backend/event_publisher.py
import httpx
import json
from typing import Dict, Any

class EventPublisher:
    """Publish events via Dapr Pub/Sub."""
    
    DAPR_URL = "http://localhost:3500"  # Dapr sidecar
    
    @classmethod
    async def publish_event(
        cls,
        topic: str,
        event_type: str,
        data: Dict[str, Any]
    ):
        """Publish event to Kafka via Dapr."""
        event = {
            "event_type": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{cls.DAPR_URL}/v1.0/publish/kafka-pubsub/{topic}",
                json=event
            )

# Usage in MCP tool handlers
async def add_task_handler(user_id: str, args: dict):
    # ... create task in DB
    
    # Publish event via Dapr
    await EventPublisher.publish_event(
        topic="task-events",
        event_type="task.created",
        data={
            "task_id": task.id,
            "user_id": user_id,
            "title": task.title
        }
    )
```

### 5.2 Notification Service (Event Consumer)

```python
# notification-service/main.py
from fastapi import FastAPI, Request
from pydantic import BaseModel
import httpx

app = FastAPI()

class CloudEvent(BaseModel):
    """Dapr CloudEvent format."""
    id: str
    source: str
    type: str
    specversion: str
    datacontenttype: str
    data: dict

@app.post("/api/events/task-events")
async def handle_task_event(event: CloudEvent):
    """Handle task events from Kafka via Dapr."""
    
    event_type = event.data.get("event_type")
    data = event.data.get("data")
    
    if event_type == "task.created":
        # Send notification for new task
        await send_notification(
            user_id=data["user_id"],
            message=f"New task created: {data['title']}"
        )
    
    return {"status": "success"}

@app.post("/api/events/reminders")
async def handle_reminder_event(event: CloudEvent):
    """Handle reminder events."""
    # Send reminder notification
    pass
```

### 5.3 Update Deployment with Dapr Annotations

```yaml
# hackathon-todo/templates/backend-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: backend
spec:
  template:
    metadata:
      annotations:
        dapr.io/enabled: "true"
        dapr.io/app-id: "backend-service"
        dapr.io/app-port: "8000"
        dapr.io/enable-api-logging: "true"
    spec:
      containers:
      - name: backend
        # ... container spec
```

## Step 6: Advanced Features Implementation

### 6.1 Recurring Tasks

```python
# backend/services/recurring_task_service.py
from dataclasses import dataclass
from enum import Enum

class RecurrenceType(Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"

@dataclass
class RecurringTask:
    base_task_id: int
    recurrence_type: RecurrenceType
    interval: int  # e.g., every 2 weeks
    end_date: Optional[datetime] = None

# When task completed, spawn next occurrence
async def handle_task_completed(task_id: int):
    recurring = get_recurring_config(task_id)
    if recurring:
        next_due = calculate_next_due_date(recurring)
        await create_next_occurrence(recurring, next_due)
```

### 6.2 Due Dates & Reminders with Dapr Jobs

```python
# Schedule reminder using Dapr Jobs API
async def schedule_reminder(task_id: int, remind_at: datetime, user_id: str):
    """Schedule reminder at exact time via Dapr Jobs."""
    
    job_name = f"reminder-task-{task_id}"
    
    await httpx.post(
        f"http://localhost:3500/v1.0-alpha1/jobs/{job_name}",
        json={
            "dueTime": remind_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "data": {
                "task_id": task_id,
                "user_id": user_id,
                "type": "reminder"
            }
        }
    )

# Handle job trigger callback
@app.post("/api/jobs/trigger")
async def handle_job_trigger(request: Request):
    """Dapr calls this at scheduled time."""
    job_data = await request.json()
    
    # Publish reminder event
    await EventPublisher.publish_event(
        topic="reminders",
        event_type="reminder.due",
        data=job_data["data"]
    )
    
    return {"status": "SUCCESS"}
```

## Step 7: CI/CD with GitHub Actions

```yaml
# .github/workflows/deploy.yml
name: Deploy to Cloud

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Build and push Docker images
      run: |
        docker build -t ${{ secrets.DOCKER_USERNAME }}/todo-backend:latest ./backend
        docker build -t ${{ secrets.DOCKER_USERNAME }}/todo-frontend:latest ./frontend
        docker push ${{ secrets.DOCKER_USERNAME }}/todo-backend:latest
        docker push ${{ secrets.DOCKER_USERNAME }}/todo-frontend:latest
    
    - name: Deploy to Kubernetes
      run: |
        doctl kubernetes cluster kubeconfig save ${{ secrets.CLUSTER_NAME }}
        helm upgrade --install hackathon-todo ./hackathon-todo \
          --set backend.image.tag=latest \
          --set frontend.image.tag=latest
```

## Step 8: Testing & Validation

- [ ] Pods running with Dapr sidecars
- [ ] Kafka topics created and accessible
- [ ] Events published to Kafka successfully
- [ ] Notification service consuming events
- [ ] Recurring tasks spawning correctly
- [ ] Reminders triggering at scheduled times
- [ ] State store persisting data
- [ ] Secrets properly configured
- [ ] CI/CD pipeline deploying successfully

## Common Issues & Solutions

### Issue: Dapr sidecar not injecting
**Solution**: Check namespace has Dapr enabled and annotations are correct

### Issue: Kafka connection failing
**Solution**: Verify credentials in secrets, check network policies

### Issue: Events not being consumed
**Solution**: Check subscription configuration, verify topic names match

### Issue: Dapr Jobs not triggering
**Solution**: Ensure callback endpoint is accessible, check job status

## Cleanup

```bash
# Delete Helm release
helm uninstall hackathon-todo

# Delete Dapr
dapr uninstall -k

# Delete cluster
doctl kubernetes cluster delete hackathon-todo
# or: gcloud container clusters delete hackathon-todo
# or: az aks delete --name hackathon-todo --resource-group hackathon-todo-rg
```

## Next Steps

1. Document deployment process
2. Create demo video
3. Submit Phase 5
4. Consider bonus features for extra points
