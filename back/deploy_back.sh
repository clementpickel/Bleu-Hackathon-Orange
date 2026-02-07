# send .env first scp .env clement@100.119.201.30:~/bleu-hackathon/

#!/usr/bin/env bash
set -euo pipefail

# === CONFIG (override on command-line: SERVER=... USER=... ./deploy_back.sh) ===
SERVER="${SERVER:-100.119.201.30}"
USER="${USER:-clement}"
LOCAL_DIR="."                       # current directory (back/)
IMAGE_NAME="bleu-hackathon-api"     # docker image name (local tag)
CONTAINER_NAME="bleu-hackathon-api"
DB_CONTAINER_NAME="bleu-hackathon-db"
PORT="${PORT:-8001}"                # host port to publish
REMOTE_PORT="8000"                  # container port exposed by the image
DB_PORT="${DB_PORT:-5432}"          # PostgreSQL port
REMOTE_SUDO="${REMOTE_SUDO:-}"      # set to "sudo" if remote docker requires sudo
SSH_OPTS="${SSH_OPTS:-}"            # optional extra ssh options

# tar filename with timestamp to avoid collisions
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
TARFILE="${IMAGE_NAME}_${TIMESTAMP}.tar"

echo "==> Deploying ${IMAGE_NAME} to ${USER}@${SERVER}"

# === 0. Pre-checks
if [ ! -f "Dockerfile" ]; then
  echo "ERROR: Dockerfile not found in current directory."
  exit 1
fi

if [ ! -f ".env" ]; then
  echo "⚠️  WARNING: .env file not found. Make sure to set environment variables on the server."
fi

# === 1. Build Docker image locally
echo "🔧 Building Docker image (${IMAGE_NAME})..."
docker build -t "${IMAGE_NAME}" .

# === 2. Save image as tar file (local)
echo "📦 Saving Docker image to ${TARFILE}..."
docker save -o "${TARFILE}" "${IMAGE_NAME}"

# ensure local tar is removed on exit
_cleanup_local() {
  rm -f "${TARFILE}" || true
}
trap _cleanup_local EXIT

# === 3. Copy image and .env to remote server
echo "📤 Copying image to ${USER}@${SERVER}:~/"
scp ${SSH_OPTS} "${TARFILE}" "${USER}@${SERVER}:~/"

# Create remote directories
echo "📁 Creating remote directories..."
ssh ${SSH_OPTS} "${USER}@${SERVER}" "mkdir -p ~/bleu-hackathon/assets"

if [ -f ".env" ]; then
  echo "📤 Copying .env file to ${USER}@${SERVER}:~/bleu-hackathon/"
  scp ${SSH_OPTS} ".env" "${USER}@${SERVER}:~/bleu-hackathon/"
fi

# Copy PDF assets if directory exists
# if [ -d "assets" ]; then
#   echo "📄 Copying PDF files to ${USER}@${SERVER}:~/bleu-hackathon/assets/"
#   scp ${SSH_OPTS} -r assets/* "${USER}@${SERVER}:~/bleu-hackathon/assets/" || echo "⚠️  Warning: Failed to copy some assets"
# fi

# === 4. Connect via SSH and run containers on remote
echo "🚀 Deploying containers on remote server (${SERVER})..."
ssh ${SSH_OPTS} "${USER}@${SERVER}" bash -e <<EOF
set -euo pipefail

TARFILE_REMOTE="\$(basename "${TARFILE}")"
IMAGE_NAME="${IMAGE_NAME}"
CONTAINER_NAME="${CONTAINER_NAME}"
DB_CONTAINER_NAME="${DB_CONTAINER_NAME}"
PORT="${PORT}"
REMOTE_PORT="${REMOTE_PORT}"
DB_PORT="${DB_PORT}"
REMOTE_SUDO="${REMOTE_SUDO:-}"

echo "-> Loading image from \${TARFILE_REMOTE}..."
\${REMOTE_SUDO} docker load -i "\${TARFILE_REMOTE}"

echo "-> Creating Docker network (if not exists)..."
\${REMOTE_SUDO} docker network create bleu-hackathon-network 2>/dev/null || true

echo "-> Recreating PostgreSQL container with fresh schema..."
echo "-> Stopping and removing existing PostgreSQL container..."
\${REMOTE_SUDO} docker stop "\${DB_CONTAINER_NAME}" >/dev/null 2>&1 || true
\${REMOTE_SUDO} docker rm "\${DB_CONTAINER_NAME}" >/dev/null 2>&1 || true

echo "-> Removing old PostgreSQL volume to force schema recreation..."
\${REMOTE_SUDO} docker volume rm bleu-hackathon-db-data >/dev/null 2>&1 || true

echo "-> Creating fresh PostgreSQL container..."
\${REMOTE_SUDO} docker run -d \\
  --name "\${DB_CONTAINER_NAME}" \\
  --network bleu-hackathon-network \\
  -e POSTGRES_USER=postgres \\
  -e POSTGRES_PASSWORD=postgres \\
  -e POSTGRES_DB=hackathon \\
  -p \${DB_PORT}:5432 \\
  -v bleu-hackathon-db-data:/var/lib/postgresql/data \\
  --restart unless-stopped \\
  postgres:15-alpine

echo "-> Waiting for PostgreSQL to be ready..."
sleep 8

echo "-> Stopping existing API container (if any)..."
\${REMOTE_SUDO} docker stop "\${CONTAINER_NAME}" >/dev/null 2>&1 || true
echo "-> Removing existing API container (if any)..."
\${REMOTE_SUDO} docker rm "\${CONTAINER_NAME}" >/dev/null 2>&1 || true

echo "-> Running new API container..."
# Load environment variables from .env file if it exists
ENV_FILE_OPT=""
if [ -f "\$HOME/bleu-hackathon/.env" ]; then
  ENV_FILE_OPT="--env-file \$HOME/bleu-hackathon/.env"
fi

\${REMOTE_SUDO} docker run -d \\
  --name "\${CONTAINER_NAME}" \\
  --network bleu-hackathon-network \\
  -p \${PORT}:\${REMOTE_PORT} \\
  -e DATABASE_URL=postgresql+psycopg://postgres:postgres@\${DB_CONTAINER_NAME}:5432/hackathon \\
  \${ENV_FILE_OPT} \\
  -v "\$HOME/bleu-hackathon/assets:/app/assets" \\
  --restart unless-stopped \\
  "\${IMAGE_NAME}"

echo "-> Removing remote tarfile..."
rm -f "\${TARFILE_REMOTE}" || true

echo "✅ Remote deployment finished!"
echo "   - Database: \${DB_CONTAINER_NAME} on port \${DB_PORT}"
echo "   - API: \${CONTAINER_NAME} on port \${PORT}"
echo "   - Access API at: http://${SERVER}:\${PORT}"
echo "   - Swagger UI: http://${SERVER}:\${PORT}/swagger"
EOF

echo ""
echo "✅ Deployment complete!"
echo "🔗 API URL: http://${SERVER}:${PORT}"
echo "📚 Swagger: http://${SERVER}:${PORT}/swagger"
echo ""
echo "⚠️  Don't forget to:"
echo "   1. Upload your PDF files to the server: scp -r assets/* ${USER}@${SERVER}:~/bleu-hackathon/assets/"
echo "   2. Verify your .env file contains all required API keys"
echo "   3. Check logs: ssh ${USER}@${SERVER} 'docker logs ${CONTAINER_NAME}'"
