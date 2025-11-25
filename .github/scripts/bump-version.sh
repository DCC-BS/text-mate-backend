#!/bin/bash

# Script to bump version in pyproject.toml
# Usage: ./bump-version.sh <major|minor|patch>

set -e

VERSION_BUMP=$1

if [ -z "$VERSION_BUMP" ]; then
  echo "Error: Version bump type not specified"
  echo "Usage: ./bump-version.sh <major|minor|patch>"
  exit 1
fi

# Bump version using uv tool, then read new version using uv version --short
uv version --bump "$VERSION_BUMP"
NEW_VERSION=$(uv version --short)
echo "New version: $NEW_VERSION"

# Commit the version bump
git add pyproject.toml
git commit -m "chore: bump version to $NEW_VERSION"

# Create and push tag
git tag "v$NEW_VERSION"
git push origin HEAD --tags

# Output the new version for GitHub Actions
echo "new_version=$NEW_VERSION"
echo "tag_name=v$NEW_VERSION"
