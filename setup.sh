#!/bin/bash

# Bank of Tina Setup Script
echo "🏦 Bank of Tina - Setup Script"
echo "================================"
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is available (either plugin or standalone)
if docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
    echo "✓ Docker and Docker Compose plugin are installed"
elif command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
    echo "✓ Docker and Docker Compose are installed"
else
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

echo ""

# Create directories if they don't exist
mkdir -p uploads database
echo "✓ Created uploads and database directories"

# Check if .env exists
if [ ! -f .env ]; then
    echo ""
    echo "⚠️  No .env file found. Creating from template..."
    
    # Check for .env.example (hidden) or env.example (visible)
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "✓ Created .env file from .env.example"
    elif [ -f env.example ]; then
        cp env.example .env
        echo "✓ Created .env file from env.example"
    else
        echo "❌ No template file found (.env.example or env.example)"
        exit 1
    fi
    
    echo ""
    echo "📝 IMPORTANT: Please edit .env file with your email settings:"
    echo "   nano .env"
    echo ""
    echo "Required settings:"
    echo "  - SECRET_KEY (change to random string)"
    echo "  - SMTP_USERNAME (your email)"
    echo "  - SMTP_PASSWORD (your email password or app password)"
    echo "  - FROM_EMAIL (your email)"
    echo ""
    read -p "Press Enter to continue after you've configured .env, or Ctrl+C to exit..."
fi

# Make scripts executable
chmod +x send_emails.sh
echo "✓ Made scripts executable"

# Build and start containers
echo ""
echo "🚀 Building and starting Docker containers..."
$DOCKER_COMPOSE up -d --build

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Bank of Tina is now running!"
    echo ""
    echo "📍 Access the app at: http://localhost:5000"
    echo ""
    echo "📧 To send weekly emails manually, run:"
    echo "   ./send_emails.sh"
    echo ""
    echo "📊 To view logs:"
    echo "   $DOCKER_COMPOSE logs -f web"
    echo ""
    echo "🛑 To stop:"
    echo "   $DOCKER_COMPOSE down"
    echo ""
else
    echo ""
    echo "❌ Failed to start Docker containers. Please check the error messages above."
    exit 1
fi
