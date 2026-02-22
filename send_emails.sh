#!/bin/bash
# Manual script to send weekly balance emails

echo "Sending weekly balance emails..."
docker exec bank-of-tina python send_weekly_email.py
echo "Done!"
