#!/usr/bin/env python3
"""Generate Helm charts for hackathon-todo deployment."""
import sys
import os
from pathlib import Path

def create_helm_chart(output_dir: str):
    """Create complete Helm chart structure."""
    base = Path(output_dir) / "hackathon-todo"
    base.mkdir(parents=True, exist_ok=True)
    
    # Chart.yaml
    (base / "Chart.yaml").write_text("""apiVersion: v2
name: hackathon-todo
description: AI-powered todo chatbot
type: application
version: 1.0.0
appVersion: "1.0"
""")
    
    # values.yaml
    (base / "values.yaml").write_text("""backend:
  image:
    repository: todo-backend
    tag: latest
    pullPolicy: IfNotPresent
  replicas: 2
  port: 8000

frontend:
  image:
    repository: todo-frontend
    tag: latest
    pullPolicy: IfNotPresent
  replicas: 2
  port: 3000

env:
  databaseUrl: ""
  openaiApiKey: ""
  betterAuthSecret: ""
""")
    
    # templates directory
    templates = base / "templates"
    templates.mkdir(exist_ok=True)
    
    # backend-deployment.yaml
    (templates / "backend-deployment.yaml").write_text("""apiVersion: apps/v1
kind: Deployment
metadata:
  name: backend
spec:
  replicas: {{ .Values.backend.replicas }}
  selector:
    matchLabels:
      app: backend
  template:
    metadata:
      labels:
        app: backend
    spec:
      containers:
      - name: backend
        image: "{{ .Values.backend.image.repository }}:{{ .Values.backend.image.tag }}"
        imagePullPolicy: {{ .Values.backend.image.pullPolicy }}
        ports:
        - containerPort: {{ .Values.backend.port }}
        env:
        - name: DATABASE_URL
          value: {{ .Values.env.databaseUrl | quote }}
        - name: OPENAI_API_KEY
          value: {{ .Values.env.openaiApiKey | quote }}
""")
    
    print(f"✅ Helm chart created at: {base}")
    print("\nNext steps:")
    print("1. Update values.yaml with your configuration")
    print(f"2. Install: helm install hackathon-todo {base}")

if __name__ == "__main__":
    output_dir = sys.argv[1] if len(sys.argv) > 1 else "./helm"
    create_helm_chart(output_dir)
