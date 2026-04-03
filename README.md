# Salience

Personal intelligence tool that pulls your X bookmarks, evaluates them against your active projects and knowledge base, and outputs ranked weekly digests to your Obsidian vault. Turns bookmarks from a graveyard of "I'll come back to this" into contextualised briefs with actionable suggestions.

## Quick Start

```bash
git clone https://github.com/henrique-lego/salience.git
cd salience
uv sync

# Configure
cp config.yaml.example config.yaml   # edit with your vault path and preferences
cp .env.example .env                  # add your API credentials

# Run
salience run              # interactive – review before writing
salience digest           # headless – write directly to vault
salience reprocess 2026-04-01  # re-evaluate a past batch
```

## Configuration

**Secrets** live in environment variables (`.env` or Keychain bridge):

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_AUTH_TOKEN` | Anthropic API key or auth token |
| `ANTHROPIC_BASE_URL` | Optional – corporate gateway URL |
| `X_API_BEARER_TOKEN` | X API bearer token |
| `X_API_CLIENT_ID` | X API client ID |
| `X_API_CLIENT_SECRET` | X API client secret |
| `X_API_USER_ID` | Your X user ID |

**macOS Keychain bridge** – add to `.zshrc` or `.envrc`:
```bash
export X_API_BEARER_TOKEN=$(security find-generic-password -s "x-api-bearer-token" -w)
export X_API_CLIENT_SECRET=$(security find-generic-password -s "x-api-client-secret" -w)
export X_API_CLIENT_ID=$(security find-generic-password -s "x-api-client-id" -w)
```

**Structure** lives in `config.yaml` – vault path, entity directories, tag vocabulary, model IDs. See `config.yaml.example` for all options.

## How It Works

1. **Harvest** – pulls new bookmarks from X API, skips already-processed ones
2. **Resolve** – follows URLs to extract article content, reconstructs threads
3. **Classify** – tags each bookmark with domains and intent (challenge/adopt/learn/inspire)
4. **Cluster** – merges duplicates, groups related bookmarks for comparative evaluation
5. **Context** – dynamically retrieves relevant files from your vault and projects
6. **Evaluate** – produces contextualised briefs (not summaries) for each bookmark
7. **Rank** – orders by relevance to your active work, challenge potential, novelty
8. **Output** – writes ranked digest to your vault with entity links and tags

## License

MIT
