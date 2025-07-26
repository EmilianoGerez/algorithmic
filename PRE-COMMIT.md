# Pre-commit Hooks Setup

This project uses [pre-commit](https://pre-commit.com/) to automatically run code quality checks before each commit.

## Quick Setup

Run the setup script to install and configure pre-commit hooks:

```bash
./setup-precommit.sh
```

## Manual Setup

If you prefer to set up manually:

```bash
# Install pre-commit
.venv/bin/pip install pre-commit

# Install the hooks to Git
.venv/bin/pre-commit install

# Test on all files
.venv/bin/pre-commit run --all-files
```

## What Gets Checked

Before each commit, these checks run automatically:

- **🔍 Ruff Linting**: Catches code style issues and potential bugs (auto-fixes when possible)
- **🎨 Ruff Formatting**: Ensures consistent code formatting
- **🏷️ MyPy Type Checking**: Validates type annotations in `core/` (strict mode)
- **✂️ Whitespace**: Removes trailing whitespace and fixes end-of-file issues
- **📄 Syntax**: Validates YAML and TOML files
- **🔀 Merge Conflicts**: Prevents committing merge conflict markers
- **📏 File Size**: Blocks commits with large files (>1MB)
- **🧪 Tests**: Runs basic tests if they exist

## Benefits

- **Catch Issues Early**: Problems are found before they reach CI/CD
- **Consistent Quality**: All commits meet the same quality standards
- **Auto-fixes**: Many issues are fixed automatically
- **Fast Feedback**: Runs only on changed files for speed
- **Team Consistency**: Everyone gets the same checks

## Commands

```bash
# Run hooks on all files
.venv/bin/pre-commit run --all-files

# Run specific hook
.venv/bin/pre-commit run ruff --all-files

# Skip hooks for a commit (use sparingly)
git commit --no-verify -m "Emergency commit"

# Update hook versions
.venv/bin/pre-commit autoupdate
```

## Configuration

The configuration is in `.pre-commit-config.yaml`. It's set up to:

- Use the latest versions of all tools
- Auto-fix issues when possible
- Focus on Python files in the `core/` directory
- Skip expensive checks in CI (they run separately)
- Fail fast to give quick feedback

## Troubleshooting

**Hook fails with "command not found":**

- Make sure you're using the virtual environment: `.venv/bin/pre-commit`

**MyPy fails with missing dependencies:**

- Install additional type stubs if needed
- Or exclude problematic files from type checking

**Hooks are too slow:**

- They only run on changed files by default
- Use `--all-files` only when necessary

**Want to skip a failing hook temporarily:**

```bash
git commit --no-verify -m "Skip hooks for this commit"
```

The pre-commit hooks help maintain code quality automatically, preventing CI failures and ensuring consistent code standards across the project.
