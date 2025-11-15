# TODO: AWS Secrets Manager Integration

## Overview
This document tracks the plan to integrate AWS Secrets Manager for storing GitHub credentials instead of using `.env` files.

## Current Implementation
Currently, GitHub authentication is handled via:
- `GITHUB_TOKEN` environment variable in `.env` file
- Optional token override in the UI for repo-specific access

## Planned Implementation

### Backend Changes
1. Add AWS Secrets Manager client library to `pyproject.toml`
2. Create new module `src/deepwiki_cli/secrets_manager.py` with functions to:
   - Retrieve GitHub token from AWS Secrets Manager
   - Fallback to `GITHUB_TOKEN` env var if AWS Secrets Manager is not configured
3. Update `src/deepwiki_cli/config.py` to use Secrets Manager when available
4. Update `src/deepwiki_cli/rag.py` to use Secrets Manager token retrieval

### Environment Variables
- `AWS_SECRETS_MANAGER_SECRET_NAME` - Name of the secret in AWS Secrets Manager
- `AWS_REGION` - AWS region (already exists, can be reused)
- `AWS_ACCESS_KEY_ID` - AWS credentials (already exists, can be reused)
- `AWS_SECRET_ACCESS_KEY` - AWS credentials (already exists, can be reused)

### Priority
- Medium priority - current `.env` approach works fine for internal use
- Consider implementing when deploying to production environments

### Notes
- Keep backward compatibility with `.env` file approach
- UI token override should still work even with Secrets Manager integration

