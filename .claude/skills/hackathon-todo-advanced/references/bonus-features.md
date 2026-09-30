# Bonus Features Implementation Guide

## Overview

Earn up to +600 bonus points by implementing advanced features:

| Bonus Feature | Points | Difficulty |
|--------------|--------|------------|
| Reusable Intelligence (Agent Skills/Subagents) | +200 | Medium |
| Cloud-Native Blueprints via Agent Skills | +200 | Medium-Hard |
| Multi-language Support (Urdu) | +100 | Easy-Medium |
| Voice Commands | +200 | Medium |
| **TOTAL** | **+600** | |

## Feature 1: Reusable Intelligence (+200 points)

### What It Is

Create reusable Claude Code **Agent Skills** and **Subagents** that can be shared across projects.

### Implementation Strategy

#### Option A: Create Agent Skill for MCP Server Scaffolding

```yaml
# .claude/skills/mcp-scaffolder/SKILL.md
---
name: mcp-scaffolder
description: Scaffold MCP servers with Official MCP SDK for task management
---

# MCP Server Scaffolding Skill

This skill generates boilerplate MCP servers with best practices.

## Usage

```
/mcp-scaffold --tools add_task,list_tasks,complete_task --database postgresql
```

## Generated Structure

```
mcp_server/
├── server.py         # Main MCP server
├── handlers.py       # Tool handlers
├── models.py         # Database models
├── config.py         # Configuration
└── tests/
    └── test_server.py
```

## Templates

The skill includes templates for:
- Basic CRUD tools
- Database integration patterns
- Error handling
- Testing setup
```

#### Option B: Create Subagent for Deployment Tasks

```python
# .claude/subagents/k8s-deployer/agent.py
"""
Subagent for Kubernetes deployment automation.

This subagent can:
- Generate Helm charts
- Create Dockerfile
- Deploy to Minikube/Cloud
- Setup Dapr components
"""

from anthropic import Anthropic
import os

class K8sDeployerAgent:
    def __init__(self):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = "claude-sonnet-4"
    
    def generate_helm_chart(self, app_name: str, components: list[str]):
        """Generate Helm chart for application."""
        prompt = f"""Generate a Helm chart for {app_name} with these components:
        {', '.join(components)}
        
        Include:
        - values.yaml with sensible defaults
        - Deployment templates for each component
        - Service templates
        - Secrets template
        - Ingress template
        """
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return response.content[0].text
    
    def generate_dockerfile(self, language: str, framework: str):
        """Generate optimized Dockerfile."""
        # ... implementation
```

### Submission Requirements

1. Create at least 2 reusable skills or 1 subagent
2. Document how to use them in README
3. Show examples of reuse across different parts of your project
4. Package skills as .skill files or subagents as Python modules

### Evaluation Criteria

- **Reusability** (60%): Can it be used in other projects?
- **Quality** (30%): Well-documented, tested, follows best practices?
- **Impact** (10%): Does it actually save development time?

## Feature 2: Cloud-Native Blueprints (+200 points)

### What It Is

Create **spec-driven deployment blueprints** that generate Kubernetes manifests, Helm charts, and Dapr components from specifications.

### Implementation Strategy

#### Blueprint Specification Format

```yaml
# blueprints/todo-chatbot.blueprint.yaml
name: todo-chatbot
version: 1.0.0

components:
  - name: backend
    type: api
    language: python
    framework: fastapi
    replicas: 2
    resources:
      requests:
        cpu: 200m
        memory: 512Mi
      limits:
        cpu: 500m
        memory: 1Gi
    env:
      - DATABASE_URL
      - OPENAI_API_KEY
    ports:
      - 8000
    dapr:
      enabled: true
      app-id: backend-service
      app-port: 8000

  - name: frontend
    type: web
    language: typescript
    framework: nextjs
    replicas: 2
    resources:
      requests:
        cpu: 100m
        memory: 256Mi
    env:
      - NEXT_PUBLIC_API_URL
    ports:
      - 3000

dapr_components:
  - type: pubsub.kafka
    name: kafka-pubsub
    metadata:
      brokers: ${KAFKA_BROKERS}
      
  - type: state.postgresql
    name: statestore
    metadata:
      connectionString: ${DATABASE_URL}

infrastructure:
  provider: digitalocean  # or gke, aks
  cluster:
    nodes: 3
    size: s-2vcpu-4gb
    region: nyc1
```

#### Blueprint Generator Agent Skill

```python
# .claude/skills/blueprint-generator/generator.py
"""
Generate Kubernetes manifests from blueprint specs.
"""

import yaml
from jinja2 import Template

class BlueprintGenerator:
    """Generate deployment artifacts from blueprints."""
    
    def generate_helm_chart(self, blueprint_path: str) -> dict[str, str]:
        """Generate complete Helm chart from blueprint."""
        
        with open(blueprint_path) as f:
            blueprint = yaml.safe_load(f)
        
        chart = {}
        
        # Generate Chart.yaml
        chart['Chart.yaml'] = self._generate_chart_yaml(blueprint)
        
        # Generate values.yaml
        chart['values.yaml'] = self._generate_values_yaml(blueprint)
        
        # Generate templates for each component
        for component in blueprint['components']:
            chart[f'templates/{component["name"]}-deployment.yaml'] = \
                self._generate_deployment(component)
            chart[f'templates/{component["name"]}-service.yaml'] = \
                self._generate_service(component)
        
        # Generate Dapr components
        if 'dapr_components' in blueprint:
            for dapr_comp in blueprint['dapr_components']:
                chart[f'dapr-components/{dapr_comp["name"]}.yaml'] = \
                    self._generate_dapr_component(dapr_comp)
        
        return chart
    
    def _generate_deployment(self, component: dict) -> str:
        """Generate Kubernetes Deployment manifest."""
        template = Template('''
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ name }}
spec:
  replicas: {{ replicas }}
  selector:
    matchLabels:
      app: {{ name }}
  template:
    metadata:
      labels:
        app: {{ name }}
      {% if dapr_enabled %}
      annotations:
        dapr.io/enabled: "true"
        dapr.io/app-id: "{{ dapr_app_id }}"
        dapr.io/app-port: "{{ dapr_app_port }}"
      {% endif %}
    spec:
      containers:
      - name: {{ name }}
        image: {{ image }}
        ports:
        {% for port in ports %}
        - containerPort: {{ port }}
        {% endfor %}
        resources:
          requests:
            cpu: {{ resources.requests.cpu }}
            memory: {{ resources.requests.memory }}
          limits:
            cpu: {{ resources.limits.cpu }}
            memory: {{ resources.limits.memory }}
        env:
        {% for env_var in env %}
        - name: {{ env_var }}
          valueFrom:
            secretKeyRef:
              name: app-secrets
              key: {{ env_var | lower | replace('_', '-') }}
        {% endfor %}
        ''')
        
        return template.render(
            name=component['name'],
            replicas=component.get('replicas', 1),
            image=f"{component['name']}:latest",
            ports=component.get('ports', []),
            resources=component.get('resources', {}),
            env=component.get('env', []),
            dapr_enabled=component.get('dapr', {}).get('enabled', False),
            dapr_app_id=component.get('dapr', {}).get('app-id', ''),
            dapr_app_port=component.get('dapr', {}).get('app-port', '')
        )
```

#### Usage with SpecifyKit Plus

```bash
# Add blueprint command to SpecifyKit Plus
uv specifyplus add-command blueprint

# Generate from blueprint
uv specifyplus blueprint generate blueprints/todo-chatbot.blueprint.yaml

# Outputs:
# - helm/hackathon-todo/
#   ├── Chart.yaml
#   ├── values.yaml
#   └── templates/
# - dapr-components/
```

### Submission Requirements

1. Create at least 1 complete blueprint specification
2. Implement blueprint generator (Python script or Agent Skill)
3. Generate working Kubernetes manifests from blueprint
4. Deploy using generated manifests successfully
5. Document blueprint format and usage

### Evaluation Criteria

- **Spec-Driven** (40%): Truly declarative, minimal manual editing needed
- **Completeness** (30%): Generates all necessary artifacts
- **Flexibility** (20%): Works for different app types/configurations
- **Documentation** (10%): Clear blueprint format documentation

## Feature 3: Multi-Language Support - Urdu (+100 points)

### What It Is

Add Urdu language support to your chatbot interface.

### Implementation Strategy

#### Backend: Language Detection & Translation

```python
# backend/services/translation_service.py
from googletrans import Translator
import langdetect

class TranslationService:
    """Handle multi-language support."""
    
    def __init__(self):
        self.translator = Translator()
        self.supported_languages = ['en', 'ur']
    
    def detect_language(self, text: str) -> str:
        """Detect language of input text."""
        try:
            return langdetect.detect(text)
        except:
            return 'en'  # Default to English
    
    def translate_to_english(self, text: str, source_lang: str) -> str:
        """Translate user input to English for agent."""
        if source_lang == 'en':
            return text
        
        result = self.translator.translate(text, src=source_lang, dest='en')
        return result.text
    
    def translate_from_english(self, text: str, target_lang: str) -> str:
        """Translate agent response to user's language."""
        if target_lang == 'en':
            return text
        
        result = self.translator.translate(text, src='en', dest=target_lang)
        return result.text

# Usage in chat endpoint
@app.post("/api/{user_id}/chat")
async def chat(user_id: str, request: ChatRequest):
    translator = TranslationService()
    
    # Detect language
    lang = translator.detect_language(request.message)
    
    # Translate to English for agent
    english_message = translator.translate_to_english(request.message, lang)
    
    # Run agent in English
    response, tools = await agent.run(user_id, messages + [
        {"role": "user", "content": english_message}
    ])
    
    # Translate response back to user's language
    translated_response = translator.translate_from_english(response, lang)
    
    return {
        "conversation_id": conv_id,
        "response": translated_response,
        "detected_language": lang
    }
```

#### Frontend: Language Selector

```typescript
// components/LanguageSelector.tsx
'use client';

import { useState } from 'react';

export function LanguageSelector() {
  const [language, setLanguage] = useState<'en' | 'ur'>('en');
  
  return (
    <select 
      value={language}
      onChange={(e) => setLanguage(e.target.value as 'en' | 'ur')}
      className="language-selector"
    >
      <option value="en">English</option>
      <option value="ur">اردو</option>
    </select>
  );
}

// UI text in Urdu
const translations = {
  en: {
    addTask: "Add task",
    viewTasks: "View tasks",
    deleteTask: "Delete task",
    placeholder: "Type your message...",
  },
  ur: {
    addTask: "کام شامل کریں",
    viewTasks: "کام دیکھیں",
    deleteTask: "کام حذف کریں",
    placeholder: "اپنا پیغام ٹائپ کریں...",
  },
};
```

### Submission Requirements

1. Support at least English and Urdu
2. Auto-detect language or provide selector
3. Translate user input for agent
4. Translate agent responses back
5. UI elements translated

## Feature 4: Voice Commands (+200 points)

### What It Is

Add voice input for todo commands using Web Speech API.

### Implementation Strategy

#### Frontend: Voice Input Component

```typescript
// components/VoiceInput.tsx
'use client';

import { useState, useEffect } from 'react';

export function VoiceInput({ onTranscript }: { onTranscript: (text: string) => void }) {
  const [isListening, setIsListening] = useState(false);
  const [recognition, setRecognition] = useState<any>(null);
  
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const SpeechRecognition = 
        (window as any).SpeechRecognition || 
        (window as any).webkitSpeechRecognition;
      
      if (SpeechRecognition) {
        const recognitionInstance = new SpeechRecognition();
        recognitionInstance.continuous = false;
        recognitionInstance.interimResults = false;
        recognitionInstance.lang = 'en-US';
        
        recognitionInstance.onresult = (event: any) => {
          const transcript = event.results[0][0].transcript;
          onTranscript(transcript);
          setIsListening(false);
        };
        
        recognitionInstance.onerror = (event: any) => {
          console.error('Speech recognition error:', event.error);
          setIsListening(false);
        };
        
        setRecognition(recognitionInstance);
      }
    }
  }, [onTranscript]);
  
  const startListening = () => {
    if (recognition) {
      recognition.start();
      setIsListening(true);
    }
  };
  
  const stopListening = () => {
    if (recognition) {
      recognition.stop();
      setIsListening(false);
    }
  };
  
  return (
    <button
      onClick={isListening ? stopListening : startListening}
      className={`voice-button ${isListening ? 'listening' : ''}`}
    >
      {isListening ? '🎤 Listening...' : '🎙️ Voice'}
    </button>
  );
}

// Usage in ChatKit
<div className="chat-input-container">
  <VoiceInput onTranscript={(text) => sendMessage(text)} />
  <ChatKit {...props} />
</div>
```

#### Voice Command Processing

```typescript
// lib/voiceCommands.ts
export function processVoiceCommand(transcript: string): {
  intent: string;
  params: Record<string, any>;
} {
  const lower = transcript.toLowerCase();
  
  // Add task
  if (lower.includes('add') || lower.includes('create')) {
    const title = lower
      .replace(/add|create|task|to|my|list/gi, '')
      .trim();
    return { intent: 'add_task', params: { title } };
  }
  
  // List tasks
  if (lower.includes('show') || lower.includes('list') || lower.includes('what')) {
    return { intent: 'list_tasks', params: {} };
  }
  
  // Complete task
  if (lower.includes('complete') || lower.includes('done')) {
    const taskId = extractTaskId(lower);
    return { intent: 'complete_task', params: { task_id: taskId } };
  }
  
  // Delete task
  if (lower.includes('delete') || lower.includes('remove')) {
    const taskId = extractTaskId(lower);
    return { intent: 'delete_task', params: { task_id: taskId } };
  }
  
  // Default: send as chat message
  return { intent: 'chat', params: { message: transcript } };
}
```

### Submission Requirements

1. Voice input button in UI
2. Speech-to-text working
3. Voice commands processed correctly
4. Visual feedback during recording
5. Works on desktop and mobile

## Submission Checklist

For each bonus feature implemented:

- [ ] Feature fully working and tested
- [ ] Code committed to GitHub
- [ ] README section explaining the feature
- [ ] Demo video showing the feature (< 90 seconds total)
- [ ] Screenshots/recordings included

## Evaluation Tips

1. **Quality over Quantity**: 1 excellent feature > 2 mediocre features
2. **Document Well**: Clear explanations boost scores significantly
3. **Show, Don't Tell**: Demo videos are crucial for bonus points
4. **Integration**: Show how it enhances the core app, not just a standalone feature
5. **Reusability**: Especially for Skills/Blueprints, emphasize reuse potential

Good luck with the bonus points! 🚀
