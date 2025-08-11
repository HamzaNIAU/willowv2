#!/bin/bash

# Suna App Startup Script
echo "🚀 Starting Suna App..."
echo "========================"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Kill any existing processes on our ports
echo -e "${YELLOW}Cleaning up old processes...${NC}"
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
lsof -ti:3000 | xargs kill -9 2>/dev/null || true

# Start Backend
echo -e "${YELLOW}Starting Backend API...${NC}"
cd /Users/hamzam/willowv2/backend
source .venv/bin/activate
uvicorn api:app --reload --host 0.0.0.0 --port 8000 > /tmp/suna_backend.log 2>&1 &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

# Give backend time to start
sleep 5

# Start Frontend
echo -e "${YELLOW}Starting Frontend...${NC}"
cd /Users/hamzam/willowv2/frontend
npm run dev > /tmp/suna_frontend.log 2>&1 &
FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID"

# Give frontend time to start
sleep 8

echo ""
echo -e "${GREEN}✨ Suna is starting up!${NC}"
echo "========================"
echo ""
echo "📍 Access Points:"
echo "  • Frontend: http://localhost:3000"
echo "  • Backend API: http://localhost:8000/docs"
echo ""
echo "📝 Logs:"
echo "  • Backend: tail -f /tmp/suna_backend.log"
echo "  • Frontend: tail -f /tmp/suna_frontend.log"
echo ""
echo "⚠️  To stop: Press Ctrl+C or run: kill $BACKEND_PID $FRONTEND_PID"
echo ""
echo "Keeping services running... Press Ctrl+C to stop."

# Trap to cleanup on exit
trap "echo 'Stopping services...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM

# Keep script running
while true; do
    sleep 1
done