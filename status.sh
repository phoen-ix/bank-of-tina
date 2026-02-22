#!/bin/bash

# Detect Docker Compose command
if docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
elif command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
else
    DOCKER_COMPOSE="docker-compose"  # fallback
fi

# Bank of Tina Status Script
echo "🏦 Bank of Tina - System Status"
echo "================================"
echo ""

# Check if container is running
if docker ps | grep -q bank-of-tina; then
    echo "✅ Application is RUNNING"
    echo ""
    
    # Show container info
    echo "📊 Container Status:"
    docker ps | grep bank-of-tina
    echo ""
    
    # Check database
    if [ -f database/bank_of_tina.db ]; then
        echo "✅ Database exists"
        db_size=$(du -h database/bank_of_tina.db | cut -f1)
        echo "   Size: $db_size"
    else
        echo "⚠️  Database not found (will be created on first use)"
    fi
    echo ""
    
    # Check uploads directory
    upload_count=$(find uploads -type f 2>/dev/null | wc -l)
    echo "📎 Receipt uploads: $upload_count files"
    if [ $upload_count -gt 0 ]; then
        uploads_size=$(du -sh uploads 2>/dev/null | cut -f1)
        echo "   Total size: $uploads_size"
    fi
    echo ""
    
    # Show recent logs
    echo "📝 Recent logs (last 10 lines):"
    docker logs bank-of-tina --tail 10
    echo ""
    
    # Show access URL
    echo "🌐 Access the app at: http://localhost:5000"
    echo ""
    
else
    echo "❌ Application is NOT RUNNING"
    echo ""
    echo "To start it, run:"
    echo "  $DOCKER_COMPOSE up -d"
    echo ""
fi

# Show useful commands
echo "💡 Useful Commands:"
echo "  View logs:        $DOCKER_COMPOSE logs -f web"
echo "  Restart:          $DOCKER_COMPOSE restart"
echo "  Stop:             $DOCKER_COMPOSE down"
echo "  Send emails:      ./send_emails.sh"
echo "  Backup database:  cp database/bank_of_tina.db database/backup_\$(date +%Y%m%d).db"
echo ""
