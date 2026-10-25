#!/bin/bash
# 5_push2dev_and_main.sh
# Push current commits to develop and main branches
# Usage: ./5_push2dev_and_main.sh

set -e  # Exit on error

# Keep window open on error
trap 'echo ""; echo "❌ Script failed! Press any key to close..."; read -n 1 -s -r' ERR EXIT

# Get directory where this script lives
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Safety check: Only run from 'develop' directory
if [[ ! "$SCRIPT_DIR" =~ "develop" ]]; then
    echo "❌ ERROR: This development script can only be run from a directory containing 'develop' in its path."
    echo "   Current directory: $SCRIPT_DIR"
    echo "   Expected: Path must contain 'develop' (e.g., ~/ai/ai4artsed_development)"
    exit 1
fi

echo "✅ Safety check passed: Running from development directory"
echo ""

# Check current branch
CURRENT_BRANCH=$(git branch --show-current)
echo "📍 Current branch: $CURRENT_BRANCH"

# Ensure we're on develop branch
if [[ "$CURRENT_BRANCH" != "develop" ]]; then
    echo "⚠️  Not on develop branch. Switching to develop..."
    git checkout develop
    if [[ $? -ne 0 ]]; then
        echo "❌ Failed to switch to develop branch"
        exit 1
    fi
fi

# Check for uncommitted changes
if [[ -n $(git status --porcelain) ]]; then
    echo ""
    echo "⚠️  WARNING: You have uncommitted changes:"
    git status --short
    echo ""
    read -p "Do you want to continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ Aborted by user"
        exit 1
    fi
fi

# Show recent commits
echo ""
echo "📝 Recent commits to be pushed:"
git log --oneline -5
echo ""

# Confirm push to develop
read -p "Push to origin/develop? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Aborted by user"
    exit 1
fi

# Push to develop
echo ""
echo "⬆️  Pushing to origin/develop..."
git push origin develop

if [[ $? -ne 0 ]]; then
    echo "❌ Failed to push to develop"
    exit 1
fi

echo "✅ Successfully pushed to develop"
echo ""

# Confirm merge to main
read -p "Merge develop into main and push? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "⚠️  Skipping main branch update"
    echo "✅ Done (develop only)"
    exit 0
fi

# Switch to main
echo ""
echo "🔀 Switching to main branch..."
git checkout main

if [[ $? -ne 0 ]]; then
    echo "❌ Failed to switch to main branch"
    git checkout develop  # Return to develop
    exit 1
fi

# Merge develop into main
echo "🔀 Merging develop into main..."
git merge develop

if [[ $? -ne 0 ]]; then
    echo "❌ Merge failed! Please resolve conflicts manually."
    git merge --abort 2>/dev/null
    git checkout develop
    exit 1
fi

# Push to main
echo "⬆️  Pushing to origin/main..."
git push origin main

if [[ $? -ne 0 ]]; then
    echo "❌ Failed to push to main"
    git checkout develop
    exit 1
fi

echo "✅ Successfully pushed to main"
echo ""

# Return to develop
echo "🔙 Returning to develop branch..."
git checkout develop

echo ""
echo "✅ All done!"
echo "   - develop: pushed ✓"
echo "   - main: merged and pushed ✓"
echo "   - current branch: develop"
echo "================================================"
read -n 1 -s -r -p "Press any key to close this window..."
echo ""
exec bash
