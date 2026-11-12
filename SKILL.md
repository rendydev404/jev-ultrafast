---
name: jev-ultrafast
description: "Use when automating web browsers at ultrafast speed via indexed DOM elements without heavy screenshot loops or external TypeSafe API keys."
metadata:
  category: browser-automation
  triggers: jev-ultrafast, jev-ag, ultrafast browser, indexed dom automation, fast web agent
---

# Jev Ultrafast Agent Skill

## Overview

`jev-ultrafast` provides a dynamic, indexed DOM action space (`CLICK`, `TYPE_TEXT`, `SELECT`, `SCROLL_UP`, `SCROLL_DOWN`, `WAIT`) with atomic DOM snapshots, occlusion checks, and page freshness guards. Through `jev-ag`, an AI coding agent acts directly as the decision policy with zero external `TYPESAFE_API_KEY` required.

## When to Use

- Use when executing fast multi-step web interactions (searches, form fills, filters, dropdowns, data extraction) with minimal latency and token usage.
- Use when screenshot-based browser loops are too slow or expensive.
- Use `--user-chrome` when the task requires authenticated sessions in the user's running Chrome browser.

## Installation

```bash
git clone https://github.com/rendydev404/jev-ultrafast.git
cd jev-ultrafast
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows: .\.venv\Scripts\Activate.ps1
pip install -e .
```

## CLI Workflow (`jev-ag`)

### 1. Open URL & Observe Indexed Elements (Popup-Free Isolated Chrome)

```bash
jev-ag --headless open "https://en.wikipedia.org/wiki/Main_Page"
```

### 2. Act on Numbered Elements

Every observation prints numbered elements (`[1]`, `[2]`, ...) and their valid operations:

```bash
# Type text into an editable input ([2])
jev-ag type 2 "Alan Turing"

# Click a button, link, or autocomplete suggestion ([3])
jev-ag click 3

# Select a native <select> dropdown option ([4:2])
jev-ag select 4:2

# Scroll viewport or wait briefly
jev-ag scroll down
jev-ag wait

# Re-observe current state (optional --screenshot <path.jpg>)
jev-ag observe

# Close the session tab cleanly when done
jev-ag close
```

### 3. Using User's Logged-In Chrome (`--user-chrome`)

Pass `--user-chrome` before the subcommand to attach to the user's primary Chrome instance:

```bash
jev-ag --user-chrome open "https://example.com"
```

Note: On first attach in Chrome 144+, Chrome shows an `"Allow remote debugging?"` prompt that the user must approve once.

## Safety & Freshness Guarantees

- Never generates brittle CSS/XPath selectors; actions bind directly to observed live DOM nodes.
- Automatically aborts with exit code `2` (`STALE_PAGE`) and refreshes the element table if the page mutated or an overlay covered the target before click/input.
- Always close the session (`jev-ag close`) once the task finishes.
