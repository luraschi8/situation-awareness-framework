# SAF: Situation Awareness Framework for OpenClaw

SAF is a high-performance architectural pattern designed to transform OpenClaw agents from reactive chatbots into **elite proactive executive assistants**. 

Standard AI memory systems often suffer from "temporal drift" (not knowing what time it is in the user's life) and "proactive spam" (repeating the same briefing multiple times). SAF solves this through a deterministic state machine and physical deduplication.

## 🚀 Key Pillars

1.  **Temporal Awareness (Step 0):** A mandatory gate that synchronizes the agent with the user's local time and day phase (e.g., `MORNING_PRIME`, `NIGHT_WATCH`) before processing any input.
2.  **Physical Deduplication:** Uses `daily-actions.json` as a persistent ledger to track proactive messages, ensuring the agent never repeats a briefing even after system restarts.
3.  **Domain Topologies:** Replaces flat memory with a structured domain-based file system (`memory/domains/`), drastically improving retrieval precision.
4.  **Behavioral Regressions:** A deterministic "blacklist" of past mistakes that the agent must read and respect in every turn.
5.  **Relevance Gate (Cognitive Filtering):** Dynamic evaluation of every proactive task against the user's current state (location, mode, overrides) to prevent irrelevant or annoying interruptions.

## 🛠️ Getting Started

SAF is designed to be "plug-and-play" with any OpenClaw instance. To install:

1.  Clone this repository.
2.  Copy the `templates/` files to your OpenClaw workspace.
3.  Add the `HEARTBEAT.md` instructions to your agent's core loop.

## 📄 Documentation

See [ARCH_SPEC.md](ARCH_SPEC.md) for a deep dive into the state machine logic and validation reports.

---
*Created by Matías Luraschi & Jarvis (v2.1 Architecture).*
