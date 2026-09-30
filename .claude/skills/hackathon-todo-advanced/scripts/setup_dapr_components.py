#!/usr/bin/env python3
"""Generate Dapr component configurations."""
import sys
from pathlib import Path

def create_dapr_components(output_dir: str):
    """Create Dapr component YAML files."""
    base = Path(output_dir)
    base.mkdir(parents=True, exist_ok=True)
    
    # Pub/Sub (Kafka)
    (base / "pubsub.yaml").write_text("""apiVersion: dapr.io/v1alpha1
kind: Component
metadata:
  name: kafka-pubsub
spec:
  type: pubsub.kafka
  version: v1
  metadata:
  - name: brokers
    value: "your-kafka-broker:9092"
  - name: consumerGroup
    value: "todo-service"
""")
    
    # State Store (PostgreSQL)
    (base / "statestore.yaml").write_text("""apiVersion: dapr.io/v1alpha1
kind: Component
metadata:
  name: statestore
spec:
  type: state.postgresql
  version: v1
  metadata:
  - name: connectionString
    value: "host=neon.tech user=... dbname=todo"
""")
    
    print(f"✅ Dapr components created at: {base}")
    print("\nNext steps:")
    print("1. Update with your actual Kafka/DB credentials")
    print(f"2. Apply: kubectl apply -f {base}/")

if __name__ == "__main__":
    output_dir = sys.argv[1] if len(sys.argv) > 1 else "./dapr-components"
    create_dapr_components(output_dir)
