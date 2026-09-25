#!/usr/bin/env bash
# ==============================================================================
# CloudPulse CLI Universal Installer for Linux & macOS
# Automatically detects OS & Architecture, installs standalone CLI,
# and configures system PATH for global execution: `cloudpulse <command>`
# ==============================================================================

set -e

# ANSI Color Codes
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${CYAN}${BOLD}"
cat << "EOF"
   ____ _                 _ ____        _           
  / ___| | ___  _   _  __| |  _ \ _   _| |___  ___  
 | |   | |/ _ \| | | |/ _` | |_) | | | | / __|/ _ \ 
 | |___| | (_) | |_| | (_| |  __/| |_| | \__ \  __/ 
  \____|_|\___/ \__,_|\__,_|_|    \__,_|_|___/\___| 
    Enterprise Cloud Cost Optimization CLI Installer
EOF
echo -e "${NC}"

# 1. Detect Operating System and Architecture
OS="$(uname -s)"
ARCH="$(uname -m)"
DISTRO="unknown"

echo -e "🔍 ${BOLD}Detecting system environment...${NC}"
case "${OS}" in
    Linux*)
        PLATFORM="linux"
        if [ -f /etc/os-release ]; then
            . /etc/os-release
            DISTRO="${ID:-linux}"
        fi
        echo -e "   • OS            : Linux (${DISTRO})"
        ;;
    Darwin*)
        PLATFORM="macos"
        DISTRO="macos"
        echo -e "   • OS            : macOS (${ARCH})"
        ;;
    MINGW*|MSYS*|CYGWIN*)
        PLATFORM="windows"
        echo -e "   • OS            : Windows (POSIX subsystem)"
        ;;
    *)
        PLATFORM="unknown"
        echo -e "   • OS            : ${OS} (Unknown)"
        ;;
esac
echo -e "   • Architecture  : ${ARCH}"

# 2. Check for Python 3 (>= 3.8)
echo -e "\n🔍 ${BOLD}Checking Python runtime...${NC}"
PYTHON_BIN=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        PY_VER="$($cmd -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || true)"
        PY_MAJOR="$(echo "$PY_VER" | cut -d. -f1)"
        PY_MINOR="$(echo "$PY_VER" | cut -d. -f2)"
        if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 8 ]; then
            PYTHON_BIN="$cmd"
            echo -e "   • Found Python  : $($cmd --version 2>&1) (${PYTHON_BIN})"
            break
        fi
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    echo -e "${RED}❌ Error: Python 3.8 or higher is required to run CloudPulse CLI.${NC}"
    echo -e "Please install Python using your system package manager:"
    if [ "$PLATFORM" = "macos" ]; then
        echo -e "   ${YELLOW}brew install python3${NC}"
    elif [ "$DISTRO" = "ubuntu" ] || [ "$DISTRO" = "debian" ]; then
        echo -e "   ${YELLOW}sudo apt-get update && sudo apt-get install -y python3 python3-pip python3-venv${NC}"
    elif [ "$DISTRO" = "fedora" ] || [ "$DISTRO" = "rhel" ] || [ "$DISTRO" = "centos" ]; then
        echo -e "   ${YELLOW}sudo dnf install -y python3 python3-pip${NC}"
    elif [ "$DISTRO" = "arch" ]; then
        echo -e "   ${YELLOW}sudo pacman -Sy --noconfirm python python-pip${NC}"
    elif [ "$DISTRO" = "alpine" ]; then
        echo -e "   ${YELLOW}apk add --no-cache python3 py3-pip${NC}"
    fi
    exit 1
fi

# 3. Setup Install Directories
INSTALL_ROOT="$HOME/.cloudpulse"
CLI_DIR="$INSTALL_ROOT/cli"
BIN_DIR="$HOME/.local/bin"
VENV_DIR="$INSTALL_ROOT/venv"

mkdir -p "$INSTALL_ROOT" "$CLI_DIR" "$BIN_DIR"

echo -e "\n📦 ${BOLD}Installing CloudPulse CLI...${NC}"

# Target Repository and Default Backend URL
REPO_URL="https://github.com/UnsettledAverage73/Cloud_Cost_Optimization.git"
DEFAULT_BACKEND="https://cloud-cost-optimization.onrender.com"

# 4. Attempt Installation:
# Strategy A: Use an isolated venv to comply with PEP 668 (Debian 12+, Ubuntu 24.04+, Arch, etc.)
INSTALLED=false

if "$PYTHON_BIN" -m venv "$VENV_DIR" 2>/dev/null; then
    echo -e "   • Created isolated Python virtual environment at ${DIM}${VENV_DIR}${NC}"
    if "$VENV_DIR/bin/pip" install --upgrade pip setuptools -q 2>/dev/null && \
       "$VENV_DIR/bin/pip" install git+"$REPO_URL" -q 2>/dev/null; then
        ln -sf "$VENV_DIR/bin/cloudpulse" "$BIN_DIR/cloudpulse"
        INSTALLED=true
        echo -e "   • Successfully installed package via Git virtualenv"
    fi
fi

# Strategy B (Fallback): Standalone launcher downloading directly from repository/backend
if [ "$INSTALLED" = false ]; then
    echo -e "   • Setting up standalone standard-library runtime..."
    RAW_BASE="https://raw.githubusercontent.com/UnsettledAverage73/Cloud_Cost_Optimization/master/backend"
    
    # Download core CLI file
    curl -fsSL "$RAW_BASE/cli_main.py" -o "$CLI_DIR/cli_main.py" 2>/dev/null || \
    curl -fsSL "$DEFAULT_BACKEND/static/cli_main.py" -o "$CLI_DIR/cli_main.py" 2>/dev/null || true

    # Create standalone runner wrapper
    cat << EOF > "$BIN_DIR/cloudpulse"
#!/usr/bin/env bash
export CLOUDPULSE_CONFIG_DIR="\$HOME/.cloudpulse"
exec "$PYTHON_BIN" "$CLI_DIR/cli_main.py" "\$@"
EOF
    chmod +x "$BIN_DIR/cloudpulse"
    INSTALLED=true
fi

# 5. Default Configuration Initialization
CONFIG_FILE="$INSTALL_ROOT/config.json"
if [ ! -f "$CONFIG_FILE" ]; then
    cat << EOF > "$CONFIG_FILE"
{
  "backend_url": "$DEFAULT_BACKEND",
  "currency": "USD",
  "installed_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF
fi

# 6. Ensure ~/.local/bin is in PATH
PATH_UPDATED=false
case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *)
        echo -e "\n⚙️  ${BOLD}Configuring system PATH...${NC}"
        EXPORT_CMD="export PATH=\"\$HOME/.local/bin:\$PATH\""
        
        # Add to appropriate shell configuration
        SHELL_NAME="$(basename "$SHELL")"
        if [ "$SHELL_NAME" = "zsh" ] && [ -f "$HOME/.zshrc" ]; then
            echo "$EXPORT_CMD" >> "$HOME/.zshrc"
            PATH_UPDATED=true
            SHELL_RC="~/.zshrc"
        elif [ -f "$HOME/.bashrc" ]; then
            echo "$EXPORT_CMD" >> "$HOME/.bashrc"
            PATH_UPDATED=true
            SHELL_RC="~/.bashrc"
        elif [ -f "$HOME/.profile" ]; then
            echo "$EXPORT_CMD" >> "$HOME/.profile"
            PATH_UPDATED=true
            SHELL_RC="~/.profile"
        fi
        export PATH="$BIN_DIR:$PATH"
        ;;
esac

# 7. Verification & Celebration
echo -e "\n${GREEN}${BOLD}========================================================================${NC}"
echo -e "${GREEN}${BOLD}🎉 CloudPulse CLI installed successfully!${NC}"
echo -e "${GREEN}${BOLD}========================================================================${NC}"
echo -e "Executable location: ${CYAN}$BIN_DIR/cloudpulse${NC}"
echo -e "Default backend    : ${CYAN}$DEFAULT_BACKEND${NC}"

if [ "$PATH_UPDATED" = true ]; then
    echo -e "\n${YELLOW}⚠️  Note: PATH updated in ${SHELL_RC}.${NC}"
    echo -e "To use immediately in this shell session, run:"
    echo -e "   ${BOLD}source ${SHELL_RC}${NC}  or  ${BOLD}export PATH=\"\$HOME/.local/bin:\$PATH\"${NC}"
fi

echo -e "\n🚀 ${BOLD}Try running these commands right now:${NC}"
echo -e "   ${CYAN}cloudpulse status${NC}           # Verify backend connectivity & system telemetry"
echo -e "   ${CYAN}cloudpulse audit${NC}            # Run FinOps spend audit, waste score, and top savings"
echo -e "   ${CYAN}cloudpulse inspect${NC}          # View complete multi-category cloud inventory"
echo -e "   ${CYAN}cloudpulse ask \"What are my highest cost drivers?\"${NC}"
echo -e "   ${CYAN}cloudpulse pov --format html --open${NC}  # Generate executive Proof-of-Value dossier"
echo ""
