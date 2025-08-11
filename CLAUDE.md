# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Suna is an open-source generalist AI agent platform with a full-stack architecture. It provides a complete AI assistant that acts on users' behalf through natural conversation, combining powerful capabilities with an intuitive interface.

## High-Level Architecture

The project consists of four main components:

1. **Frontend** (Next.js/React): Chat interface and dashboard at `/frontend`
2. **Backend API** (Python/FastAPI): REST endpoints and LLM integration at `/backend`
3. **Agent Docker**: Isolated execution environment for every agent with browser automation and tool integration
4. **Supabase Database**: PostgreSQL with Row Level Security, authentication, and real-time features

### Key Architectural Patterns

- **Agent System**: Versioned agents with JSONB configuration storage, workflows, and triggers
- **Tool Execution**: Dual schema decorators (OpenAPI + XML) with consistent ToolResult patterns
- **Authentication**: Supabase Auth with JWT validation
- **Background Jobs**: Dramatiq for async processing, QStash for scheduling
- **Real-time Updates**: Supabase subscriptions for live data
- **Monitoring**: Langfuse tracing, Sentry error tracking, Prometheus metrics
- **MCP Integration**: Custom MCP servers in `/suna-youtube-mcp/` for extended functionality

## Common Development Commands

### Frontend Development

```bash
cd frontend

# Development server with Turbopack
npm run dev

# Production build
npm run build

# Linting
npm run lint

# Format code
npm run format

# Check formatting
npm run format:check
```

### Backend Development

```bash
cd backend

# Start FastAPI server
uvicorn api:app --reload --host 0.0.0.0 --port 8000

# Run tests (when available)
pytest

# Install dependencies with uv
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .

# Run background worker (Dramatiq)
uv run dramatiq --processes 2 --threads 2 run_agent_background
```

### Full Stack Development

```bash
# Start all services using Docker Compose
python start.py

# Initial setup wizard (creates .env files, configures services)
python setup.py

# Run database migrations
python run_migrations.py

# Docker compose commands
docker-compose -f docker-compose.yaml up -d
docker-compose -f docker-compose.yaml down
```

### Local Development (without Docker)

```bash
# Start Supabase locally (requires Supabase CLI)
supabase start

# Apply migrations to local Supabase
cd backend/supabase
for file in migrations/*.sql; do
  psql "postgresql://postgres:postgres@localhost:54322/postgres" -f "$file"
done
```

## Critical File Locations

### Frontend Structure
- `/frontend/src/app/` - Next.js App Router pages
- `/frontend/src/components/agents/` - Agent-related UI components
- `/frontend/src/hooks/react-query/` - React Query hooks for data fetching
- `/frontend/src/lib/` - Utilities and configurations

### Backend Structure
- `/backend/api.py` - Main FastAPI application entry point
- `/backend/agent/` - Core AI agent implementation
- `/backend/agent/tools/` - Tool implementations for agents
- `/backend/agent/suna/` - Agent orchestration and repository logic
- `/backend/services/` - Business logic services (billing, email, LLM, etc.)
- `/backend/composio_integration/` - Composio service integrations
- `/backend/triggers/` - Event-driven trigger system
- `/backend/supabase/migrations/` - Database migration files
- `/backend/credentials/` - Credential management API
- `/backend/sandbox/` - Sandbox environment API
- `/backend/templates/` - Template service

### Configuration Files
- `/backend/.env` - Backend environment variables
- `/frontend/.env.local` - Frontend environment variables
- `/docker-compose.yaml` - Docker services configuration
- `/backend/pyproject.toml` - Python dependencies
- `/frontend/package.json` - Node.js dependencies

## Database Schema Patterns

- **Migrations**: Located in `/backend/supabase/migrations/`, use idempotent SQL
- **Key Tables**: `agents`, `agent_versions`, `threads`, `messages`, `agent_workflows`, `agent_triggers`
- **RLS Policies**: Database-level access control for multi-tenancy
- **JSONB Storage**: Agent configurations and metadata stored as JSONB

## Tool System Implementation

Tools follow a dual-schema pattern:
1. OpenAPI decorators for API documentation
2. XML schema for LLM tool descriptions
3. Consistent ToolResult return format
4. Located in `/backend/agent/tools/`

Example tool structure:
```python
@tool_decorator(
    name="tool_name",
    description="Tool description",
    parameters=OpenAPISchema  # For API docs
)
def tool_function(params):
    # Implementation
    return ToolResult(...)
```

## Environment Variables

### Essential Backend Variables
- `ENV_MODE`: local/development/production
- `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`
- `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`
- `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `MODEL_TO_USE`
- `API_KEY_SECRET`, `MCP_CREDENTIAL_ENCRYPTION_KEY`
- `DAYTONA_API_KEY`, `DAYTONA_SERVER_URL` (for sandboxed execution)

### Essential Frontend Variables
- `NEXT_PUBLIC_ENV_MODE`
- `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `NEXT_PUBLIC_BACKEND_URL`
- `NEXT_PUBLIC_URL`

## Testing Strategy

- Frontend: Unit tests for components, integration tests for API calls
- Backend: pytest for Python tests (test files not yet created)
- E2E: Critical user flow testing
- Performance: Agent execution benchmarking

## Security Considerations

- JWT validation without signature check for Supabase tokens
- Row Level Security (RLS) for database access control
- Credential encryption for sensitive API keys
- Input validation using Pydantic models
- Isolated Docker environments for agent execution

## Integration Points

- **LLM Providers**: Anthropic, OpenAI, and others via LiteLLM
- **Search**: Tavily for web search capabilities
- **Web Scraping**: Firecrawl for content extraction
- **Background Jobs**: QStash for workflows and scheduling, Dramatiq for async processing
- **Monitoring**: Langfuse for LLM tracing, Sentry for errors, Prometheus for metrics
- **MCP Servers**: Custom Model Context Protocol servers for extended functionality
- **Composio**: Third-party service integrations

## Development Workflow Tips

1. Always check existing patterns in similar files before implementing new features
2. Use structured logging with context throughout the stack
3. Handle loading and error states properly in the frontend
4. Follow TypeScript strict mode in frontend, use type hints in Python backend
5. Test agent tools in isolation before integration
6. Use Redis caching for frequently accessed data
7. Implement proper timeout handling for agent operations
8. Use the `/backend/flags/flags.py` for feature flags
9. Follow the dual-schema pattern when creating new tools
10. Ensure database migrations are idempotent and reversible