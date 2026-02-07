#!/bin/bash
# Verify you're using the custom TLDR version with web/serverless support

echo "🔍 Checking TLDR installation..."
echo ""

# Check which tldr is being used
TLDR_PATH=$(which tldr)
echo "📍 Using tldr from: $TLDR_PATH"

# Check if it's the editable install
if [[ "$TLDR_PATH" == *"llm-tldr/.venv"* ]] || [[ "$TLDR_PATH" == *"llm-tldr/venv"* ]]; then
    echo "✅ Using editable install from local repo"
else
    echo "⚠️  Not using local repo - may not have custom changes"
fi

echo ""

# Check current branch
cd "$(dirname "$0")"
BRANCH=$(git branch --show-current 2>/dev/null)
if [ -n "$BRANCH" ]; then
    echo "📌 Current branch: $BRANCH"
    if [ "$BRANCH" = "feature/web-serverless-entry-points" ]; then
        echo "✅ On the correct feature branch"
    else
        echo "⚠️  Not on feature/web-serverless-entry-points branch"
        echo "   Run: git checkout feature/web-serverless-entry-points"
    fi
else
    echo "❌ Not in a git repository"
fi

echo ""

# Check if custom module exists
if python3 -c "from tldr.project_config import parse_serverless_handlers" 2>/dev/null; then
    echo "✅ Custom modules loaded (project_config.py found)"
else
    echo "❌ Custom modules NOT found"
    exit 1
fi

echo ""

# Check PyYAML dependency
if python3 -c "import yaml" 2>/dev/null; then
    echo "✅ PyYAML dependency installed"
else
    echo "❌ PyYAML NOT installed"
    echo "   Run: pip install pyyaml>=6.0"
    exit 1
fi

echo ""
echo "🎉 All checks passed! You're using the custom TLDR version."
echo ""
echo "Features available:"
echo "  • Parse serverless.yml for Lambda handlers"
echo "  • Track JSX component usage (<Button /> as call)"
echo "  • Recognize Next.js entry points (getServerSideProps, etc.)"
echo "  • Hardcoded serverless patterns (handler, lambda_handler)"
echo ""
echo "Test it:"
echo "  tldr dead /path/to/your/project --lang typescript"
