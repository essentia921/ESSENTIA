#!/bin/bash
set -e

echo "=== Post-merge setup ==="

echo "--- Installing Python dependencies from pyproject.toml..."
python3 -c "
import tomllib
with open('pyproject.toml', 'rb') as f:
    data = tomllib.load(f)
for dep in data.get('project', {}).get('dependencies', []):
    print(dep)
" | xargs uv pip install --quiet

echo "--- Installing frontend dependencies..."
cd frontend && npm install --silent

echo "--- Building frontend..."
npm run build --silent

echo "=== Done ==="
