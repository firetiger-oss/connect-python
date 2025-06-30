# Release Management

This document describes the automated release workflow for the connect-python package.

## Overview

The project uses a Python release workflow with:
- Dynamic versioning from Git tags using `hatch-vcs`
- Automated CI/CD via GitHub Actions
- PyPI trusted publishing for uploads
- Single-command releases using `bump-my-version`

## Version Management

### Dynamic Versioning
Versions are automatically generated from Git tags using `hatch-vcs`:
- **Release versions**: `1.2.3` (from tag `v1.2.3`)
- **Pre-release versions**: `1.2.3-rc1` (from tag `v1.2.3-rc1`)
- **Dev versions**: `1.2.4.dev7+g1a2b3c4` (commits after last tag)

### Version File
The `src/connectrpc/_version.py` file is maintained by `bump-my-version` for compatibility but the actual version used in builds comes from Git tags.

## Release Types

### 1. Development Releases (Automatic)
- **Trigger**: Every commit to `main` branch
- **Destination**: TestPyPI
- **Workflow**: `.github/workflows/dev-release.yml`
- **Version format**: `0.4.1.dev7+g1a2b3c4`

Development releases happen automatically - no manual intervention
required, and no tags.

### 2. Release Candidates
- **Trigger**: `bump-my-version` commands with RC versions
- **Destination**: PyPI
- **Workflow**: `.github/workflows/release.yml`
- **Version format**: `1.2.3-rc1`, `1.2.3-rc2`, etc.
- **Tag format**: `v1.2.3-rc1`, etc

### 3. Final Releases
- **Trigger**: `bump-my-version` commands
- **Destination**: PyPI
- **Workflow**: `.github/workflows/release.yml`
- **Version format**: `1.2.3`, `1.4.0`, etc.
- **Tag format**: `v1.2.3`, etc

## Release Commands

We use `bump-my-version`. This command automatically:
1. Updates `src/connectrpc/_version.py`
2. Commits the version change
3. Creates a Git tag (e.g., `v0.4.1`)
4. Pushes the commit and tag
5. Triggers the GitHub Actions release workflow

### Publishing a new release candidate
```bash
# Start RC for next minor version
uv run bump-my-version bump minor --new-version 1.3.0-rc1

# Or start RC for next patch version
uv run bump-my-version bump patch --new-version 1.2.4-rc1

# Bump RC number (rc1 → rc2, rc2 → rc3, etc.)
uv run bump-my-version bump build

# Finalize RC to final release (1.2.4-rc2 → 1.2.4)
uv run bump-my-version bump release
```

### Releasing a new version
```bash
# Patch release (0.4.0 → 0.4.1)
uv run bump-my-version bump patch

# Minor release (0.4.1 → 0.5.0)
uv run bump-my-version bump minor

# Major release (0.5.0 → 1.0.0)
uv run bump-my-version bump major
```

## GitHub Actions Workflows

### Dev Release Workflow (`.github/workflows/dev-release.yml`)
**Triggers**: Push to `main` branch
**Actions**:
1. Install dependencies with `uv`
2. Run tests (`pytest`)
3. Run linting (`ruff`, `mypy`)
4. Build package (`uv build`)
5. Publish to TestPyPI

### Release Workflow (`.github/workflows/release.yml`)
**Triggers**: Git tags starting with `v`
**Actions**:
1. Install dependencies with `uv`
2. Run tests (`pytest`)
3. Run linting (`ruff`, `mypy`)
4. Build package (`uv build`)
5. Publish to PyPI via trusted publishing
6. Create GitHub release (pre-release if tag contains `-`)

## Testing the Setup

### Local Testing
```bash
# Install dependencies
uv sync --group dev

# Test version detection (works after editable install)
uv pip install -e .
uv run python -c "from importlib.metadata import version; print(version(connect-python'))"

# Test build
uv build

# Test bump-my-version configuration
uv run bump-my-version show
```

### Workflow Testing
```bash
# Test dev release (will publish to TestPyPI)
echo "# Test change" >> README.md
git add README.md
git commit -m "Test dev release"
git push origin main

# Test production release
uv run bump-my-version bump patch
```

## Release Checklist

### For Each Release
- [ ] Ensure all tests pass: `uv run pytest`
- [ ] Ensure linting passes: `uv run ruff check && uv run mypy src`
- [ ] Choose appropriate version bump (patch/minor/major)
- [ ] Run: `uv run bump-my-version bump <type>`
- [ ] Verify release appears on PyPI and GitHub releases
- [ ] Test installation: `pip install connect-python==<new-version>`

### Emergency Fixes
If a release needs to be pulled or fixed:
1. Yank the problematic release from PyPI (if possible)
2. Create a new patch version with the fix
3. Release the fixed version immediately

## Best Practices

1. **Always test locally** before releasing
2. **Use semantic versioning** (major.minor.patch)
3. **Write meaningful commit messages** (they appear in dev versions)
4. **Tag pre-releases** for testing before final releases
5. **Monitor GitHub Actions** for workflow failures
6. **Keep this documentation updated** as the process evolves
