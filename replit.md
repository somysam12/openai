# Overview

This project is a Telegram AI chatbot designed for multilingual conversational AI, offering persistence of conversation history and administrative features for user management. It supports interactions in Hindi, English, and Hinglish, aiming for a friendly and engaging user experience. The application features a dual deployment architecture: a Python-based bot utilizing `python-telegram-bot` and OpenAI's API (deployable to Render.com), and a Node.js/TypeScript implementation built with the Mastra framework and Inngest for advanced agent capabilities and web chat interfaces. Key capabilities include real-time token usage tracking with an admin dashboard, comprehensive API key rotation, automated message management, live group messaging sessions for administrators, **Super Knowledge Management System**, and **Multi-Account Pyrogram DM Bot Manager**.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Dual Architecture Approach

The system employs a dual architecture to support both traditional bot deployments and modern agent-based workflows. A Python-based bot (`main.py`) provides core functionality for simpler deployments, while a TypeScript/Mastra framework implementation offers advanced features and workflow orchestration, including web chat interfaces.

## Python Implementation (Primary)

-   **Application Framework**: Python 3 with `python-telegram-bot` (v21.0.1), using an event-driven command and message handler pattern.
-   **Conversation Storage**: SQLite3 (`chat_history.db`) for persistent conversation history, storing user messages, bot responses, timestamps, and user metadata.
-   **AI Integration**: OpenAI API for AI responses, defaulting to GPT-4. Context is maintained by retrieving the last 10 messages per user. Includes configurable base URL support and personality-driven prompt engineering.
-   **Authentication & Authorization**: Environment variable-based admin ID for privileged operations and database-tracked blocked users.
-   **Token Tracking**: Implements live token usage tracking, per-key statistics, daily auto-reset, and smart status indicators, all accessible via an admin panel.
-   **API Key Management**: Smart API key rotation on errors (401, 403, 429), sharing `api_key_stats` with the Node.js bot for unified monitoring.
-   **Admin Panel Features**: Allows viewing and editing automated bot messages, managing API keys, viewing user chat histories, deleting chat histories, and initiating live group messaging sessions.
-   **Knowledge Base**: Prioritizes a knowledge base over keyword-based responses, enhancing AI prompts for comprehensive understanding.
-   **Super Knowledge System**: Priority-based knowledge management with scope targeting (Main Bot/DM Bot/Both), status control (active/inactive), and highest priority in AI prompts. Allows admin to add mandatory directives that override all other knowledge.
-   **Multi-Account Manager**: Database-backed Pyrogram account management with UI controls for adding, activating/deactivating, and deleting up to 5 personal Telegram accounts for automated DM replies across multiple accounts simultaneously.

## Multi-Account Pyrogram Architecture

-   **Database Schema**: `pyrogram_accounts` table tracks phone numbers, account names, session strings, authentication status, activation state, reply counts, and error messages.
-   **Admin Interface**: Full CRUD operations via admin panel - add accounts with phone validation, toggle activation status, view statistics, delete accounts, and monitor errors.
-   **Backend Runner**: `multi_account_manager.py` script runs multiple Pyrogram clients concurrently, respecting `is_active` and `is_authenticated` flags from database.
-   **Message Handling**: DM messages processed through keyword matching first, then AI responses using shared knowledge base (filtered by `dm_only` or `both` scope).
-   **Lifecycle Management**: Admin controls (activate/deactivate/delete) update database flags; runner queries flags on startup to determine which accounts to run.
-   **Error Tracking**: Authentication failures, session errors, and API issues stored in database and displayed in admin UI.

## TypeScript/Mastra Implementation (Advanced)

-   **Framework Architecture**: Mastra framework (`@mastra/core`) for agent orchestration, with Inngest handling event-driven workflow execution.
-   **Agent Configuration**: `telegramChatAgent` with dynamic instructions, PostgreSQL-based conversation memory (`@mastra/memory`), and OpenAI GPT-4 integration. Supports multi-step reasoning.
-   **Workflow System**: Step-based workflows via Inngest, specifically `telegramChatWorkflow` for processing messages through the agent and sending replies. Includes retry logic for error handling.
-   **Storage Architecture**: Primarily PostgreSQL via `@mastra/pg`, with LibSQL support (`@mastra/libsql`), utilizing a shared connection pool.
-   **Web Interface**: Static HTML/CSS/JS served from `/public` for a modern UI with chat bubbles and client-generated session IDs. RESTful endpoints handle message processing.
-   **Trigger System**: Webhook-based Telegram message handling (`/webhooks/telegram/action`) routed through Inngest functions for decoupled trigger registration.
-   **Extensibility**: Designed with a tool system (`createTool()`) for reusable functions with Zod-based validation, dynamic agent instructions, pluggable memory backends, and composable workflow steps.

## Deployment Strategy

-   **Render.com Deployment (Python)**: Configured as a Web Service with `pip install -r requirements.txt` and `python start_both_bots.py` as start commands. Compatible with Render's free tier.
-   **Multi-Process Architecture**: `start_both_bots.py` runs main bot and multi-account manager in separate threads. Multi-account manager only starts if `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` are set.
-   **Environment Variables**: Uses `TELEGRAM_BOT_TOKEN`, `OPENAI_API_KEY`, `ADMIN_ID`, `DATABASE_URL`, `OPENAI_BASE_URL`, `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, and `NODE_ENV` for configuration.

# External Dependencies

-   **Telegram**: `python-telegram-bot` library (v21.0.1) and Telegram Bot API for bot interaction.
-   **Pyrogram**: User account automation library for multi-account DM management.
-   **OpenAI**: OpenAI API for AI capabilities (GPT-4 or compatible models).
-   **Render.com**: Deployment platform for the Python application.
-   **Inngest**: Event-driven workflow engine for the TypeScript application.
-   **PostgreSQL**: Primary database for the TypeScript application (via `@mastra/pg` and `@mastra/memory`).
-   **SQLite3**: Local file-based database (`chat_history.db`) for the Python application, storing conversations, knowledge, and Pyrogram account data.
-   **LibSQL**: Alternative database support for the TypeScript application (via `@mastra/libsql`).
-   **Mastra Framework**: `@mastra/core`, `@mastra/pg`, `@mastra/memory` for the TypeScript implementation.

# Recent Changes (October 20, 2025)

## Super Knowledge Management System
- Added priority-based knowledge system with `priority='super'` flag
- Implemented scope targeting: `main_only`, `dm_only`, or `both`
- Created admin UI for adding, managing, and deleting super knowledge entries
- Integrated super knowledge as highest priority in AI prompts
- Added status control (active/inactive) for knowledge entries

## Multi-Account Pyrogram DM Bot Manager
- Created `pyrogram_accounts` database table with session tracking
- Built admin panel for adding up to 5 phone numbers with account names
- Implemented duplicate phone number validation
- Added activate/deactivate toggle controls per account
- Created `multi_account_manager.py` backend runner for concurrent Pyrogram clients
- Integrated knowledge base filtering by scope (dm_only/both)
- Added keyword matching and AI response handling for DM bots
- Implemented reply count tracking and error message storage
- Added delete account functionality with confirmation