# Local Development Setup (Without Docker)

This guide will help you run the Suna app locally without Docker, using native installations.

## Prerequisites

### 1. Install Required Software

#### macOS (using Homebrew):
```bash
# Install PostgreSQL
brew install postgresql@15
brew services start postgresql@15

# Install Redis
brew install redis
brew services start redis

# Install Python 3.11+
brew install python@3.11

# Install Node.js 20+
brew install node

# Install uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### Linux (Ubuntu/Debian):
```bash
# Install PostgreSQL
sudo apt update
sudo apt install postgresql postgresql-contrib

# Install Redis
sudo apt install redis-server

# Install Python 3.11+
sudo apt install python3.11 python3.11-venv python3-pip

# Install Node.js 20+
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install nodejs

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Step 1: Set up PostgreSQL Database

```bash
# Connect to PostgreSQL
psql -U postgres

# Create database and user
CREATE DATABASE suna_local;
CREATE USER suna_user WITH PASSWORD 'suna_password';
GRANT ALL PRIVILEGES ON DATABASE suna_local TO suna_user;
ALTER USER suna_user CREATEDB;
\q
```

## Step 2: Install Supabase CLI and Initialize Local Instance

```bash
# Install Supabase CLI
brew install supabase/tap/supabase  # macOS
# OR
npm install -g supabase  # All platforms

# Initialize Supabase locally
cd /Users/hamzam/willowv2
supabase init

# Start Supabase locally (this will use Docker internally but provides local Supabase)
supabase start
```

After running `supabase start`, you'll get output with your local Supabase credentials. Save these!

Example output:
```
API URL: http://localhost:54321
GraphQL URL: http://localhost:54321/graphql/v1
DB URL: postgresql://postgres:postgres@localhost:54322/postgres
Studio URL: http://localhost:54323
Inbucket URL: http://localhost:54324
JWT secret: your-super-secret-jwt-secret
anon key: eyJ...
service_role key: eyJ...
```

## Step 3: Run Database Migrations

```bash
# Apply all migrations to your local Supabase
cd /Users/hamzam/willowv2/backend/supabase
for file in migrations/*.sql; do
  psql "postgresql://postgres:postgres@localhost:54322/postgres" -f "$file"
done
```

## Step 4: Configure Backend Environment

Create `/Users/hamzam/willowv2/backend/.env`:

```bash
# Environment Mode
ENV_MODE=local

# Use the credentials from supabase start output
SUPABASE_URL=http://localhost:54321
SUPABASE_ANON_KEY=<your-anon-key-from-supabase-start>
SUPABASE_SERVICE_ROLE_KEY=<your-service-role-key-from-supabase-start>

# Redis (local)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_SSL=false

# LLM Providers (add your API keys)
ANTHROPIC_API_KEY=<your-anthropic-key>
OPENAI_API_KEY=<your-openai-key>
MODEL_TO_USE=claude-3-5-sonnet-20241022

# Optional: Web Search & Scraping
TAVILY_API_KEY=<your-tavily-key>
FIRECRAWL_API_KEY=<your-firecrawl-key>

# Generate a random secret for API keys
API_KEY_SECRET=$(openssl rand -hex 32)
MCP_CREDENTIAL_ENCRYPTION_KEY=$(openssl rand -hex 32)

# Leave these empty for local development
DAYTONA_API_KEY=
DAYTONA_SERVER_URL=
DAYTONA_TARGET=

# QStash (optional for local)
QSTASH_URL=
QSTASH_TOKEN=
WEBHOOK_BASE_URL=http://localhost:8000

# Leave monitoring disabled for local
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=
```

## Step 5: Configure Frontend Environment

Create `/Users/hamzam/willowv2/frontend/.env.local`:

```bash
NEXT_PUBLIC_ENV_MODE=LOCAL
NEXT_PUBLIC_SUPABASE_URL=http://localhost:54321
NEXT_PUBLIC_SUPABASE_ANON_KEY=<your-anon-key-from-supabase-start>
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000/api
NEXT_PUBLIC_URL=http://localhost:3000

# Optional
NEXT_PUBLIC_GOOGLE_CLIENT_ID=
OPENAI_API_KEY=
KORTIX_ADMIN_API_KEY=
EDGE_CONFIG=
```

## Step 6: Install Dependencies

### Backend Dependencies:
```bash
cd /Users/hamzam/willowv2/backend

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .
```

### Frontend Dependencies:
```bash
cd /Users/hamzam/willowv2/frontend
npm install
```

## Step 7: Start the Services

### Terminal 1 - Redis:
```bash
redis-server
```

### Terminal 2 - Backend API:
```bash
cd /Users/hamzam/willowv2/backend
source .venv/bin/activate
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

### Terminal 3 - Background Worker (optional but recommended):
```bash
cd /Users/hamzam/willowv2/backend
source .venv/bin/activate
uv run dramatiq --processes 2 --threads 2 run_agent_background
```

### Terminal 4 - Frontend:
```bash
cd /Users/hamzam/willowv2/frontend
npm run dev
```

## Step 8: Access the Application

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000/docs
- Supabase Studio: http://localhost:54323

## Troubleshooting

### Common Issues:

1. **Port already in use**: 
   - Change ports in the configuration files
   - Or kill existing processes: `lsof -i :PORT` and `kill -9 PID`

2. **Database connection errors**:
   - Ensure PostgreSQL is running: `brew services list` or `systemctl status postgresql`
   - Check credentials match between .env and actual database

3. **Redis connection errors**:
   - Ensure Redis is running: `redis-cli ping` (should return PONG)

4. **Missing dependencies**:
   - Backend: `uv pip install <package-name>`
   - Frontend: `npm install <package-name>`

5. **Agent tools not working**:
   - Note: Without Docker/Daytona, browser automation and sandboxed code execution won't work
   - The chat interface and basic LLM features will still function

## Minimal Setup (Just Chat Interface)

If you just want to test the chat interface without all features:

1. Skip Daytona configuration
2. Use SQLite instead of PostgreSQL (modify Supabase config)
3. Skip Redis (some caching features won't work)
4. Only configure essential API keys (ANTHROPIC_API_KEY or OPENAI_API_KEY)

## Next Steps

- Create a test account at http://localhost:3000/auth
- Create your first agent in the dashboard
- Test the chat interface
- For production features like browser automation, consider using the Docker setup