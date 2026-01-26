#!/bin/bash
set -e

# Recreate docs dir
rm -rf docs/html
mkdir -p docs/html
cp style.css docs/html/

# Identify available versions from schemas/ directory
VERSIONS=$(ls -d schemas/v* | xargs -n 1 basename)

# Determine latest version (sort -V for version sort)
LATEST_VERSION=$(echo "$VERSIONS" | sort -V | tail -n 1)

echo "Found versions: $VERSIONS"
echo "Latest version: $LATEST_VERSION"

# Build each version
# We pass the full list of available versions (flat string) to the generator.
# Using python list replacement formatting in generator requires list, argparse nargs='*' takes multiple args.
# So we pass them space separated.

ALL_VERSIONS="$VERSIONS latest"

for VER in $VERSIONS; do
echo "Building HTML for $VER..."
python3 bin/generate_html.py --version "$VER" --web-schemas --available-versions $ALL_VERSIONS
done

# Create 'latest' alias
echo "Creating latest alias from $LATEST_VERSION..."
cp -r "docs/html/$LATEST_VERSION" "docs/html/latest"

# Prepare Schemas for Publishing in docs/html/schemas
echo "Publishing schemas..."
mkdir -p docs/html/schemas

for VER in $VERSIONS; do
mkdir -p docs/html/schemas/$VER
cp schemas/$VER/*.json docs/html/schemas/$VER/
done

# Also for latest
mkdir -p docs/html/schemas/latest
cp schemas/$LATEST_VERSION/*.json docs/html/schemas/latest/

# Generate Landing Page
echo "Generating landing page..."
python3 bin/generate_index.py --out docs/html --versions $VERSIONS

echo "Documentation Rebuild Complete."
