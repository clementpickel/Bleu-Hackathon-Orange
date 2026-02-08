# send .env first scp .env clement@100.119.201.30:~/bleu-hackathon/

#!/usr/bin/env bash
set -euo pipefail

# === CONFIG (override on command-line: SERVER=... USER=... ./deploy_back.sh) ===
SERVER="${SERVER:-100.119.201.30}"
USER="${USER:-clement}"
BACK_DIR="."                        # current directory (back/)
FRONT_DIR="../projet-bleu"          # frontend directory
BACK_IMAGE_NAME="bleu-hackathon-api"
FRONT_IMAGE_NAME="bleu-hackathon-frontend"
BACK_CONTAINER_NAME="bleu-hackathon-api"
FRONT_CONTAINER_NAME="bleu-hackathon-frontend"
DB_CONTAINER_NAME="bleu-hackathon-db"
BACK_PORT="${BACK_PORT:-8001}"      # backend host port
BACK_REMOTE_PORT="8000"             # backend container port
FRONT_PORT="${FRONT_PORT:-3001}"    # frontend host port
FRONT_REMOTE_PORT="80"              # frontend container port (nginx)
DB_PORT="${DB_PORT:-5432}"          # PostgreSQL port
REMOTE_SUDO="${REMOTE_SUDO:-}"      # set to "sudo" if remote docker requires sudo
SSH_OPTS="${SSH_OPTS:-}"            # optional extra ssh options

# tar filenames with timestamp to avoid collisions
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACK_TARFILE="${BACK_IMAGE_NAME}_${TIMESTAMP}.tar"
FRONT_TARFILE="${FRONT_IMAGE_NAME}_${TIMESTAMP}.tar"

echo "==> Deploying Backend + Frontend to ${USER}@${SERVER}"

# === 0. Pre-checks
if [ ! -f "Dockerfile" ]; then
  echo "ERROR: Backend Dockerfile not found in current directory."
  exit 1
fi

if [ ! -f "${FRONT_DIR}/Dockerfile" ]; then
  echo "ERROR: Frontend Dockerfile not found in ${FRONT_DIR}."
  exit 1
fi

if [ ! -f ".env" ]; then
  echo "⚠️  WARNING: .env file not found. Make sure to set environment variables on the server."
fi

# === 1. Build Backend Docker image locally
echo "🔧 Building Backend Docker image (${BACK_IMAGE_NAME})..."
docker build -t "${BACK_IMAGE_NAME}" .

# === 2. Build Frontend Docker image locally
echo "🔧 Building Frontend Docker image (${FRONT_IMAGE_NAME})..."
docker build -t "${FRONT_IMAGE_NAME}" "${FRONT_DIR}"

# === 3. Save images as tar files (local)
echo "📦 Saving Backend Docker image to ${BACK_TARFILE}..."
docker save -o "${BACK_TARFILE}" "${BACK_IMAGE_NAME}"

echo "📦 Saving Frontend Docker image to ${FRONT_TARFILE}..."
docker save -o "${FRONT_TARFILE}" "${FRONT_IMAGE_NAME}"

# ensure local tars are removed on exit
_cleanup_local() {
  rm -f "${BACK_TARFILE}" "${FRONT_TARFILE}" || true
}
trap _cleanup_local EXIT

# === 4. Copy images and .env to remote server
echo "📤 Copying Backend image to ${USER}@${SERVER}:~/"
scp ${SSH_OPTS} "${BACK_TARFILE}" "${USER}@${SERVER}:~/"

echo "📤 Copying Frontend image to ${USER}@${SERVER}:~/"
scp ${SSH_OPTS} "${FRONT_TARFILE}" "${USER}@${SERVER}:~/"

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

# === 5. Connect via SSH and run containers on remote
echo "🚀 Deploying containers on remote server (${SERVER})..."
ssh ${SSH_OPTS} "${USER}@${SERVER}" bash -e <<EOF
set -euo pipefail

BACK_TARFILE_REMOTE="\$(basename "${BACK_TARFILE}")"
FRONT_TARFILE_REMOTE="\$(basename "${FRONT_TARFILE}")"
BACK_IMAGE_NAME="${BACK_IMAGE_NAME}"
FRONT_IMAGE_NAME="${FRONT_IMAGE_NAME}"
BACK_CONTAINER_NAME="${BACK_CONTAINER_NAME}"
FRONT_CONTAINER_NAME="${FRONT_CONTAINER_NAME}"
DB_CONTAINER_NAME="${DB_CONTAINER_NAME}"
BACK_PORT="${BACK_PORT}"
BACK_REMOTE_PORT="${BACK_REMOTE_PORT}"
FRONT_PORT="${FRONT_PORT}"
FRONT_REMOTE_PORT="${FRONT_REMOTE_PORT}"
DB_PORT="${DB_PORT}"
REMOTE_SUDO="${REMOTE_SUDO:-}"

echo "-> Loading Backend image from \${BACK_TARFILE_REMOTE}..."
\${REMOTE_SUDO} docker load -i "\${BACK_TARFILE_REMOTE}"

echo "-> Loading Frontend image from \${FRONT_TARFILE_REMOTE}..."
\${REMOTE_SUDO} docker load -i "\${FRONT_TARFILE_REMOTE}"

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
\${REMOTE_SUDO} docker stop "\${BACK_CONTAINER_NAME}" >/dev/null 2>&1 || true
echo "-> Removing existing API container (if any)..."
\${REMOTE_SUDO} docker rm "\${BACK_CONTAINER_NAME}" >/dev/null 2>&1 || true

echo "-> Running new API container..."
# Load environment variables from .env file if it exists
ENV_FILE_OPT=""
if [ -f "\$HOME/bleu-hackathon/.env" ]; then
  ENV_FILE_OPT="--env-file \$HOME/bleu-hackathon/.env"
fi

\${REMOTE_SUDO} docker run -d \\
  --name "\${BACK_CONTAINER_NAME}" \\
  --network bleu-hackathon-network \\
  -p \${BACK_PORT}:\${BACK_REMOTE_PORT} \\
  -e DATABASE_URL=postgresql+psycopg://postgres:postgres@\${DB_CONTAINER_NAME}:5432/hackathon \\
  \${ENV_FILE_OPT} \\
  -v "\$HOME/bleu-hackathon/assets:/app/assets" \\
  --restart unless-stopped \\
  "\${BACK_IMAGE_NAME}"

echo "-> Stopping existing Frontend container (if any)..."
\${REMOTE_SUDO} docker stop "\${FRONT_CONTAINER_NAME}" >/dev/null 2>&1 || true
echo "-> Removing existing Frontend container (if any)..."
\${REMOTE_SUDO} docker rm "\${FRONT_CONTAINER_NAME}" >/dev/null 2>&1 || true

echo "-> Running new Frontend container..."
\${REMOTE_SUDO} docker run -d \\
  --name "\${FRONT_CONTAINER_NAME}" \\
  --network bleu-hackathon-network \\
  -p \${FRONT_PORT}:\${FRONT_REMOTE_PORT} \\
  --restart unless-stopped \\
  "\${FRONT_IMAGE_NAME}"

echo "-> Removing remote tarfiles..."
rm -f "\${BACK_TARFILE_REMOTE}" "\${FRONT_TARFILE_REMOTE}" || true

echo "✅ Remote deployment finished!"
echo "   - Database: \${DB_CONTAINER_NAME} on port \${DB_PORT}"
echo "   - Backend API: \${BACK_CONTAINER_NAME} on port \${BACK_PORT}"
echo "   - Frontend: \${FRONT_CONTAINER_NAME} on port \${FRONT_PORT}"
echo "   - Access Frontend at: http://${SERVER}:\${FRONT_PORT}"
echo "   - Access Backend API at: http://${SERVER}:\${BACK_PORT}"
echo "   - Swagger UI: http://${SERVER}:\${BACK_PORT}/swagger"
EOF

echo ""
echo "✅ Deployment complete!"
echo "🌐 Frontend URL: http://${SERVER}:${FRONT_PORT}"
echo "🔗 Backend API URL: http://${SERVER}:${BACK_PORT}"
echo "📚 Swagger: http://${SERVER}:${BACK_PORT}/swagger"
echo ""
echo "⚠️  Don't forget to:"
echo "   1. Upload your PDF files to the server: scp -r assets/* ${USER}@${SERVER}:~/bleu-hackathon/assets/"
echo "   2. Verify your .env file contains all required API keys"
echo "   3. Check Backend logs: ssh ${USER}@${SERVER} 'docker logs ${BACK_CONTAINER_NAME}'"
echo "   4. Check Frontend logs: ssh ${USER}@${SERVER} 'docker logs ${FRONT_CONTAINER_NAME}'"
