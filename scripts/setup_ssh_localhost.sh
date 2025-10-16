#!/bin/bash
# Setup SSH for localhost testing

set -e

echo "========================================="
echo "SSH Localhost Setup for Testing"
echo "========================================="

# Check if SSH server is installed
if ! command -v sshd &> /dev/null; then
    echo ""
    echo "SSH server not found. Installing..."
    echo "Please run:"
    echo "  sudo apt-get update"
    echo "  sudo apt-get install -y openssh-server"
    echo ""
    read -p "Install now? (requires sudo) [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo apt-get update
        sudo apt-get install -y openssh-server
    else
        echo "Skipping installation. Please install manually."
        exit 1
    fi
fi

# Check if SSH key exists
if [ ! -f ~/.ssh/id_rsa ]; then
    echo ""
    echo "Generating SSH key..."
    ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N ""
    echo "✓ SSH key generated"
fi

# Add key to authorized_keys
if [ ! -f ~/.ssh/authorized_keys ]; then
    mkdir -p ~/.ssh
    touch ~/.ssh/authorized_keys
    chmod 700 ~/.ssh
    chmod 600 ~/.ssh/authorized_keys
fi

if ! grep -q "$(cat ~/.ssh/id_rsa.pub)" ~/.ssh/authorized_keys 2>/dev/null; then
    echo ""
    echo "Adding SSH key to authorized_keys..."
    cat ~/.ssh/id_rsa.pub >> ~/.ssh/authorized_keys
    chmod 600 ~/.ssh/authorized_keys
    echo "✓ SSH key authorized"
else
    echo "✓ SSH key already authorized"
fi

# Start SSH server if not running
if ! pgrep -x sshd > /dev/null; then
    echo ""
    echo "Starting SSH server..."
    if command -v systemctl &> /dev/null; then
        sudo systemctl start ssh || sudo systemctl start sshd
        echo "✓ SSH server started"
    else
        echo "Please start SSH server manually:"
        echo "  sudo service ssh start"
        exit 1
    fi
else
    echo "✓ SSH server already running"
fi

# Test SSH connection
echo ""
echo "Testing SSH connection to localhost..."
if ssh -o BatchMode=yes -o ConnectTimeout=5 localhost whoami &> /dev/null; then
    echo "✓ SSH to localhost working!"
    echo ""
    echo "========================================="
    echo "Setup complete! You can now run:"
    echo "  uv run python test_ssh_localhost.py"
    echo "========================================="
else
    echo "✗ SSH connection failed. Please check:"
    echo "  1. SSH server is running: sudo systemctl status ssh"
    echo "  2. Port 22 is open: sudo netstat -tuln | grep :22"
    echo "  3. Firewall allows localhost: sudo ufw status"
    exit 1
fi
