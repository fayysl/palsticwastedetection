# Phase 3: OpenAI ChatKit Setup & Configuration

## Overview

OpenAI ChatKit provides a pre-built chat UI component that:
- Handles message rendering
- Manages conversation state on frontend
- Sends messages to your backend
- Displays streaming responses
- Works with OpenAI's hosted infrastructure

## Prerequisites

- OpenAI API account with domain allowlist access
- Deployed frontend URL (for domain allowlist)
- Working backend chat endpoint

## Step 1: Domain Allowlist Configuration

⚠️ **CRITICAL**: ChatKit will NOT work until you complete domain allowlist setup.

### 1.1 Deploy Frontend First

Deploy your Next.js app to get a production URL:

```bash
# Push to GitHub
git push origin main

# Deploy to Vercel
vercel --prod

# Note your URL
# Example: https://hackathon-todo-asadullah.vercel.app
```

### 1.2 Add Domain to OpenAI Allowlist

1. Go to: https://platform.openai.com/settings/organization/security/domain-allowlist
2. Click **"Add domain"**
3. Enter your frontend URL (without trailing slash):
   ```
   https://hackathon-todo-asadullah.vercel.app
   ```
4. Save changes
5. **Copy the domain key** provided by OpenAI

### 1.3 Configure Environment Variables

Add to your `.env.local`:

```bash
# Frontend environment
NEXT_PUBLIC_OPENAI_DOMAIN_KEY=your-domain-key-here
NEXT_PUBLIC_API_URL=https://your-backend-api.com
```

## Step 2: ChatKit Installation

```bash
cd frontend
npm install @openai/chatkit
# or
yarn add @openai/chatkit
```

## Step 3: Basic ChatKit Implementation

### 3.1 Create Chat Page

```typescript
// app/chat/page.tsx
'use client';

import { ChatKit } from '@openai/chatkit';
import '@openai/chatkit/styles.css';
import { useState } from 'react';

export default function ChatPage() {
  const [conversationId, setConversationId] = useState<number | null>(null);

  return (
    <div className="h-screen">
      <ChatKit
        // Required props
        apiKey={process.env.NEXT_PUBLIC_OPENAI_DOMAIN_KEY!}
        
        // Custom backend integration
        onSendMessage={async (message) => {
          return await sendMessageToBackend(message, conversationId);
        }}
        
        // Optional: Custom greeting
        greeting={{
          title: "Todo Assistant",
          description: "Manage your tasks with natural language",
        }}
        
        // Optional: Suggested prompts
        suggestions={[
          "Add buy groceries to my list",
          "What's on my todo list?",
          "Mark task 1 as complete",
          "Delete the meeting task",
        ]}
      />
    </div>
  );
}

async function sendMessageToBackend(
  message: string,
  conversationId: number | null
): Promise<ChatKitResponse> {
  // Get user from auth
  const userId = getUserId(); // From Better Auth session
  
  // Call your FastAPI backend
  const response = await fetch(
    `${process.env.NEXT_PUBLIC_API_URL}/api/${userId}/chat`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${getAuthToken()}`,
      },
      body: JSON.stringify({
        conversation_id: conversationId,
        message: message,
      }),
    }
  );
  
  if (!response.ok) {
    throw new Error('Failed to send message');
  }
  
  const data = await response.json();
  
  // Update conversation ID for next message
  if (data.conversation_id) {
    setConversationId(data.conversation_id);
  }
  
  // Return in ChatKit expected format
  return {
    content: data.response,
    role: 'assistant',
  };
}
```

### 3.2 Add Authentication Check

```typescript
// app/chat/page.tsx (updated)
'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { getSession } from '@/lib/auth'; // Better Auth

export default function ChatPage() {
  const router = useRouter();
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [userId, setUserId] = useState<string>('');
  
  useEffect(() => {
    async function checkAuth() {
      const session = await getSession();
      if (!session) {
        router.push('/login');
      } else {
        setIsAuthenticated(true);
        setUserId(session.user.id);
      }
    }
    checkAuth();
  }, [router]);
  
  if (!isAuthenticated) {
    return <div>Loading...</div>;
  }
  
  return (
    <div className="h-screen">
      {/* ChatKit component here */}
    </div>
  );
}
```

## Step 4: Advanced Configuration

### 4.1 Custom Message Rendering

```typescript
<ChatKit
  // ... other props
  
  renderMessage={(message) => {
    if (message.role === 'assistant' && message.tool_calls) {
      return (
        <div>
          <p>{message.content}</p>
          <div className="text-xs text-gray-500 mt-2">
            Tools used: {message.tool_calls.map(t => t.tool).join(', ')}
          </div>
        </div>
      );
    }
    return <p>{message.content}</p>;
  }}
/>
```

### 4.2 Streaming Responses (Optional)

If your backend supports streaming:

```typescript
// Backend: FastAPI with streaming
from fastapi.responses import StreamingResponse

@app.post("/api/{user_id}/chat")
async def chat_stream(user_id: str, request: ChatRequest):
    async def generate():
        # Stream agent responses
        async for chunk in agent.stream(user_id, request.message):
            yield f"data: {json.dumps({'content': chunk})}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")

// Frontend: Handle streaming
<ChatKit
  onSendMessage={async (message) => {
    const response = await fetch(apiUrl, {
      method: 'POST',
      // ... headers
    });
    
    const reader = response.body.getReader();
    let fullResponse = '';
    
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      
      const chunk = new TextDecoder().decode(value);
      // Parse SSE format
      const lines = chunk.split('\n');
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = JSON.parse(line.slice(6));
          fullResponse += data.content;
        }
      }
    }
    
    return { content: fullResponse, role: 'assistant' };
  }}
/>
```

### 4.3 Error Handling

```typescript
<ChatKit
  onSendMessage={async (message) => {
    try {
      return await sendMessageToBackend(message, conversationId);
    } catch (error) {
      console.error('Chat error:', error);
      return {
        content: "Sorry, I encountered an error. Please try again.",
        role: 'assistant',
        error: true,
      };
    }
  }}
  
  onError={(error) => {
    console.error('ChatKit error:', error);
    // Show user-friendly error toast
  }}
/>
```

## Step 5: Styling & Customization

### 5.1 Custom Theme

```typescript
// app/chat/page.tsx
import '@openai/chatkit/styles.css';

<div className="h-screen bg-gray-50">
  <style jsx global>{`
    .chatkit-container {
      max-width: 800px;
      margin: 0 auto;
    }
    
    .chatkit-message-user {
      background: #2563eb;
      color: white;
    }
    
    .chatkit-message-assistant {
      background: white;
      border: 1px solid #e5e7eb;
    }
  `}</style>
  
  <ChatKit {...props} />
</div>
```

### 5.2 Mobile Responsiveness

```css
/* globals.css */
@media (max-width: 768px) {
  .chatkit-container {
    height: 100vh;
    max-width: 100%;
  }
  
  .chatkit-input {
    font-size: 16px; /* Prevents zoom on iOS */
  }
}
```

## Step 6: Testing

### 6.1 Local Development

For local development (`localhost:3000`), domain allowlist is typically not required:

```bash
# Run frontend
cd frontend
npm run dev

# Test chat at http://localhost:3000/chat
```

### 6.2 Production Testing Checklist

- [ ] Domain added to OpenAI allowlist
- [ ] Domain key configured in environment
- [ ] Backend chat endpoint working
- [ ] Authentication working (JWT token sent)
- [ ] Conversation persists across page refreshes
- [ ] Multiple conversations can be created
- [ ] Tool calls displayed in debug mode

### 6.3 Debug Mode

Enable verbose logging:

```typescript
<ChatKit
  debug={true}  // Shows tool calls and API requests
  {...props}
/>
```

## Common Issues & Solutions

### Issue: "Domain not allowed" error
**Symptoms**: ChatKit refuses to load, console shows domain error
**Solution**:
1. Verify domain added to allowlist (exact match, no trailing slash)
2. Wait 5 minutes after adding domain (propagation time)
3. Hard refresh browser (Ctrl+Shift+R)
4. Check NEXT_PUBLIC_OPENAI_DOMAIN_KEY is set correctly

### Issue: Messages not sending
**Symptoms**: Clicking send does nothing, no network request
**Solution**:
1. Check browser console for errors
2. Verify API URL is correct in environment variables
3. Test backend endpoint directly with curl/Postman
4. Check CORS headers allow frontend domain

### Issue: Conversations not persisting
**Symptoms**: New conversation created on every message
**Solution**:
1. Ensure conversation_id returned from backend is stored in state
2. Pass conversation_id to subsequent requests
3. Check database to verify conversation is saved
4. Use React DevTools to inspect conversation state

### Issue: Authentication failing
**Symptoms**: 401 Unauthorized from backend
**Solution**:
1. Verify JWT token is attached to request headers
2. Check token expiration (Better Auth tokens expire)
3. Test token validation manually with curl
4. Ensure user_id matches between token and URL

### Issue: ChatKit not rendering
**Symptoms**: Blank page, no errors
**Solution**:
1. Check ChatKit CSS is imported: `import '@openai/chatkit/styles.css'`
2. Verify container has height: `className="h-screen"`
3. Check React version compatibility (needs React 18+)
4. Clear Next.js cache: `rm -rf .next`

## Performance Optimization

### Lazy Loading

```typescript
// Lazy load ChatKit to reduce initial bundle
import dynamic from 'next/dynamic';

const ChatKit = dynamic(
  () => import('@openai/chatkit').then(mod => mod.ChatKit),
  { ssr: false }
);
```

### Conversation History Limit

```typescript
// Limit loaded messages to prevent performance issues
const [messages, setMessages] = useState<Message[]>([]);

useEffect(() => {
  // Only load last 50 messages
  async function loadHistory() {
    const history = await fetchConversationHistory(conversationId);
    setMessages(history.slice(-50));
  }
  loadHistory();
}, [conversationId]);
```

## Next Steps

1. Complete MCP server implementation
2. Test agent with various queries
3. Deploy frontend with domain allowlist
4. Verify end-to-end conversation flow
5. Move to Phase 4: Kubernetes deployment
