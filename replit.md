# Overview

This is a Telegram AI chatbot application with dual deployment architectures. The primary implementation is a Python-based bot using `python-telegram-bot` and OpenAI's API, deployable to Render.com. Additionally, there's a Node.js/TypeScript implementation using the Mastra framework with Inngest for workflow orchestration, supporting web chat interfaces and advanced agent capabilities.

The bot provides multilingual conversational AI with conversation history persistence, admin features for user management, and context-aware responses. It's designed to be friendly and engaging, with special support for Hindi, English, and Hinglish interactions.

# User Preferences

Preferred communication style: Simple, everyday language.

# Recent Changes

## October 19, 2025 - Enhanced Keyword System with Knowledge Base Integration

**Feature**: Keywords can now intelligently use the Knowledge Base for responses.

**Implementation**:
- When adding a keyword without a custom response (e.g., just `price`), the bot uses AI + Knowledge Base to generate intelligent context-aware responses
- When adding a keyword with a custom response (e.g., `price | ₹500`), the bot sends that exact response
- This allows admins to create smart keywords that leverage stored knowledge rather than fixed responses
- Updated admin panel UI to clearly show which keywords use AI vs direct responses

**User Benefit**: Admin can add keywords like "price", "features", "support" without writing responses, and the bot will automatically search the knowledge base and respond intelligently.

# System Architecture

## Dual Architecture Approach

**Problem**: Supporting both traditional deployment and modern agent-based workflows with different infrastructure requirements.

**Solution**: Implemented two parallel architectures:
1. Python-based standalone bot (main.py) for simple deployments
2. TypeScript/Mastra framework for advanced features and workflow orchestration

**Rationale**: Provides flexibility for different deployment scenarios while maintaining core functionality.

## Python Implementation (Primary)

### Application Framework
- **Technology**: Python 3 with `python-telegram-bot` library (v21.0.1)
- **Entry Point**: `main.py` serves as the main bot application
- **Pattern**: Event-driven command and message handlers

### Conversation Storage
- **Database**: SQLite3 with local file storage (`chat_history.db`)
- **Schema**: Stores user messages, bot responses, timestamps, and user metadata
- **Approach**: Simple relational storage for conversation history without external dependencies
- **Trade-offs**: SQLite provides simplicity and portability but limited scalability for high-concurrency scenarios

### AI Integration
- **Provider**: OpenAI API (configurable base URL support)
- **Model**: Defaults to GPT-4 or compatible models
- **Context Management**: Retrieves last 10 messages per user for conversation continuity
- **Prompt Engineering**: Personality-driven instructions for multilingual, friendly interactions

### Authentication & Authorization
- **Admin System**: Environment variable-based admin ID for privileged operations
- **User Blocking**: Database-tracked blocked users with admin-only management
- **Mechanism**: Simple ID-based checks without complex role systems

## TypeScript/Mastra Implementation (Advanced)

### Framework Architecture
- **Core**: Mastra framework (@mastra/core v0.20.0) for agent orchestration
- **Workflow Engine**: Inngest for event-driven workflow execution
- **Pattern**: Agent-based architecture with step-based workflows

### Agent Configuration
- **Agent**: `telegramChatAgent` with dynamic instructions
- **Memory**: PostgreSQL-based conversation memory via `@mastra/memory`
- **Model**: OpenAI GPT-4 with configurable endpoints
- **Features**: Multi-step reasoning (maxSteps: 5) for complex interactions

### Workflow System
- **Pattern**: Step-based workflows using Inngest
- **Key Workflow**: `telegramChatWorkflow` - processes messages through agent and sends responses
- **Steps**: 
  1. `use-agent`: Generate AI response with conversation context
  2. `send-telegram-reply`: Deliver response back to user
- **Error Handling**: Configurable retry logic (3 attempts in production, 0 in development)

### Storage Architecture
- **Primary Storage**: PostgreSQL via `@mastra/pg`
- **Alternative**: LibSQL support via `@mastra/libsql`
- **Connection**: Shared connection pool pattern (`sharedPostgresStorage`)
- **Configuration**: Environment-based connection strings with localhost fallback

### Web Interface
- **Frontend**: Static HTML/CSS/JS served from `/public`
- **Style**: Gradient-based modern UI with chat bubbles
- **Session Management**: Client-generated session IDs for web users
- **API**: RESTful endpoints for message handling

### Trigger System
- **Telegram Integration**: Webhook-based message handling via `/webhooks/telegram/action`
- **Event Routing**: Inngest function wrapping for API routes
- **Pattern**: Decoupled trigger registration for extensibility

## Development Features

### TypeScript Configuration
- **Target**: ES2022 with ES module system
- **Module Resolution**: Bundler mode for modern tooling
- **Strict Mode**: Enabled for type safety
- **Build**: No emit mode (using tsx/mastra build tools)

### Development Tools
- **Runtime**: tsx for TypeScript execution
- **CLI**: Mastra CLI for development and deployment
- **Format**: Prettier for code formatting
- **Type Checking**: Standalone tsc checks

## Deployment Strategy

### Render.com Deployment (Python)
- **Service Type**: Web Service
- **Build**: `pip install -r requirements.txt`
- **Start**: `python main.py`
- **Environment**: Free tier compatible
- **Configuration**: Environment variables for secrets

### Environment Variables
- **TELEGRAM_BOT_TOKEN**: Bot authentication
- **OPENAI_API_KEY**: AI service access
- **ADMIN_ID**: Administrative user identification
- **DATABASE_URL**: PostgreSQL connection (TypeScript version)
- **OPENAI_BASE_URL**: Custom API endpoint (optional)
- **NODE_ENV**: Environment detection (production/development)

## Extensibility Design

### Tool System (Mastra)
- **Pattern**: `createTool()` for reusable functions
- **Schema**: Zod-based input/output validation
- **Example**: `exampleTool` demonstrates tool creation pattern
- **Integration**: Tools can be attached to agents

### Agent Extensibility
- **Instructions**: Async function support for dynamic behavior
- **Model Selection**: Runtime-configurable model choice
- **Tools**: Dynamic tool attachment per agent
- **Memory**: Pluggable memory backends

### Workflow Composition
- **Steps**: Reusable step definitions with schemas
- **Chaining**: Sequential step execution
- **Context**: Thread-based conversation tracking
- **Error Handling**: Step-level retry and error management