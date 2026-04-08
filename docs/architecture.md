# Architecture

## System overview

```mermaid
graph TB
    subgraph Input ["X Bookmarks"]
        API["X API<br/>bearer token + OAuth"]
    end

    subgraph Pipeline ["8-Step Pipeline"]
        H["1. Harvest<br/>pull new bookmarks"]
        R["2. Resolve<br/>fetch article content,<br/>reconstruct threads"]
        C["3. Classify<br/>domains + intent<br/>(challenge/adopt/learn/inspire)"]
        CL["4. Cluster<br/>dedup + group<br/>related bookmarks"]
        CX["5. Context<br/>retrieve vault files,<br/>project context"]
        E["6. Evaluate<br/>contextualised briefs<br/>(not summaries)"]
        RK["7. Rank<br/>relevance, challenge<br/>potential, novelty"]
        O["8. Output<br/>ranked digest<br/>to vault"]
    end

    subgraph External ["External Context"]
        V["Obsidian Vault<br/>daily notes, concepts,<br/>project files"]
        IP["Interest Profile<br/>salience/interest-profile.md"]
    end

    subgraph Output ["Vault Output"]
        DG["salience/YYYY-MM-DD-digest.md"]
        IPU["interest-profile.md<br/>(updated)"]
    end

    API --> H
    H --> R --> C --> CL
    V -.->|dynamic retrieval| CX
    IP -.->|preferences| E
    CL --> CX --> E --> RK --> O
    O --> DG
    O --> IPU
```

## Pipeline detail

Each step maps to a module in `src/salience/`:

| Step | Module | Input | Output | LLM? |
|------|--------|-------|--------|------|
| Harvest | `harvest.py` | X API bookmarks | Raw bookmark list | No |
| Resolve | `resolve.py` | Bookmark URLs | Extracted article content, thread reconstructions | No |
| Classify | `classify.py` | Article content | Domain tags + intent labels | Yes |
| Cluster | `cluster.py` | Classified bookmarks | Deduplicated groups | No |
| Context | `context.py` | Bookmark topics | Relevant vault files, project context | No |
| Evaluate | `evaluate.py` | Bookmark + context | Contextualised briefs ("what it means for you") | Yes |
| Rank | `rank.py` | Evaluated briefs | Ordered by relevance, challenge potential, novelty | Yes |
| Output | `format.py` + `output.py` | Ranked briefs | Vault-formatted digest with entity links | No |

Three steps use LLM calls (classify, evaluate, rank). The rest are deterministic.

## Three-tier deduplication

```mermaid
graph LR
    B["Bookmarks"] --> URL["URL-level<br/>exact match on<br/>resolved URL"]
    URL --> SEM["Semantic<br/>LLM similarity<br/>within clusters"]
    SEM --> CROSS["Cross-batch<br/>compare against<br/>previous digests"]
```

Prevents the same article from appearing across multiple weekly digests even if bookmarked via different URLs or retweets.

## Context assembly

```mermaid
graph TD
    BK["Bookmark topics"] --> SCAN["Scan vault"]
    SCAN --> DN["Recent daily notes<br/>(last 7 days)"]
    SCAN --> CN["Matching concept notes"]
    SCAN --> PJ["Active project files"]
    SCAN --> IP["Interest profile"]
    DN & CN & PJ & IP --> ASM["Assemble context<br/>budget-aware"]
    ASM --> EVAL["Feed to evaluator"]
```

Context is assembled dynamically per bookmark – only relevant vault files are included, respecting context window budget. The interest profile provides stable preference signals; vault files provide recency.

## Configuration split

```
config.yaml          Structure – vault path, entity dirs, tags, model IDs, pipeline settings
.env                 Secrets – API keys, tokens (never committed)
macOS Keychain       Optional – bridge secrets via security commands
```

## Key design decisions

- **Briefs, not summaries** – the evaluator produces "what this means for you" contextualised against your active work, not neutral abstractions
- **Interest profile as feedback loop** – the profile tracks which domains, authors, and topics you engage with over time, shaping future ranking
- **Three LLM calls, not eight** – only classify, evaluate, and rank use the LLM. Everything else is deterministic. Keeps cost predictable and debugging tractable
- **Vault-native output** – digests are markdown with wikilinks and tags from the controlled vocabulary, ready for Obsidian and compilable by `/ingest`
