#!/bin/bash
set -e

echo "🚀 CarryMem One-Click Install"
echo "================================"
echo ""

echo "📋 Checking Python version..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.9 or higher."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "✅ Found Python $PYTHON_VERSION"

if ! command -v pip3 &> /dev/null && ! python3 -m pip --version &> /dev/null; then
    echo "❌ pip not found. Please install pip."
    exit 1
fi

echo ""
echo "📦 Upgrading pip..."
python3 -m pip install --upgrade pip 2>/dev/null || pip3 install --upgrade pip 2>/dev/null || true

echo ""
echo "📦 Installing CarryMem..."

# 卸载旧版本（如果存在）
pip3 uninstall carrymem -y 2>/dev/null || true

# 安装新版本
if [ -f "setup.py" ]; then
    # 从源码安装（开发模式）
    echo "📁 Installing from source (development mode)..."
    pip3 install -e .
else
    # 从 PyPI 安装
    echo "📦 Installing from PyPI..."
    pip3 install carrymem
fi

echo ""
echo "✅ Verifying installation..."

# 验证命令是否可用
if command -v carrymem &> /dev/null; then
    echo "✅ Command 'carrymem' is available!"
    carrymem version
else
    echo "⚠️  Command 'carrymem' not found in PATH"
    echo ""
    echo "💡 Adding Python bin to PATH..."
    
    # 获取 Python bin 目录
    PYTHON_BIN=$(python3 -m site --user-base)/bin
    
    # 检测 shell
    if [ -n "$ZSH_VERSION" ]; then
        SHELL_RC="$HOME/.zshrc"
    elif [ -n "$BASH_VERSION" ]; then
        SHELL_RC="$HOME/.bashrc"
    else
        SHELL_RC="$HOME/.profile"
    fi
    
    # 添加到 PATH
    if ! grep -q "$PYTHON_BIN" "$SHELL_RC" 2>/dev/null; then
        echo "" >> "$SHELL_RC"
        echo "# CarryMem - Added by install script" >> "$SHELL_RC"
        echo "export PATH=\"\$PATH:$PYTHON_BIN\"" >> "$SHELL_RC"
        echo "✅ Added to $SHELL_RC"
    fi
    
    # 临时添加到当前 session
    export PATH="$PATH:$PYTHON_BIN"
    
    # 再次验证
    if command -v carrymem &> /dev/null; then
        echo "✅ Command 'carrymem' is now available!"
        carrymem version
    else
        echo "⚠️  Please restart your terminal or run:"
        echo "    source $SHELL_RC"
        echo ""
        echo "Or use the full command:"
        echo "    python3 -m carrymem.cli"
    fi
fi

echo ""
echo "🗄️  Initializing database..."
python3 -m carrymem.cli init 2>/dev/null || echo "✅ Database already initialized"

echo ""
echo "🔌 MCP Configuration"
echo "-------------------"

# 检测 Claude Desktop
CLAUDE_CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
if [ -f "$CLAUDE_CONFIG" ]; then
    echo "✅ Detected Claude Desktop"
    read -p "Configure MCP for Claude Desktop? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        python3 -m carrymem.cli setup-mcp --tool claude 2>/dev/null || echo "⚠️  MCP setup command not fully implemented yet"
        echo "💡 Manual setup: Add to $CLAUDE_CONFIG"
        echo '   "carrymem": {'
        echo '     "command": "python3",'
        echo '     "args": ["-m", "carrymem.integration.layer2_mcp"]'
        echo '   }'
    fi
else
    echo "ℹ️  Claude Desktop not detected"
fi

echo ""
echo "🎉 Installation Complete!"
echo "========================="
echo ""
echo "Quick Start:"
echo "  carrymem add \"I prefer dark mode\""
echo "  carrymem list"
echo "  carrymem search \"theme\""
echo ""
echo "Documentation:"
echo "  https://github.com/lulin70/carrymem"
echo ""
echo "Need help? Run: carrymem help"
echo ""
