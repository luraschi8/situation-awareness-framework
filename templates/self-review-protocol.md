# SAF Self-Review Protocol

You are performing a scheduled knowledge audit of this workspace.

- **Review timestamp:** {{ timestamp }}
- **Last review:** {{ last_review_timestamp }}
- **Mode:** {{ review_mode }}
- **Staleness threshold:** {{ staleness_threshold_days }} days

---

## Permissions

{{ permissions }}

---

## Your Tasks

### 1. Staleness Audit

Review the domain audit table below. For files not modified in
{{ staleness_threshold_days }}+ days (marked as stale), read them and
assess whether the content is still accurate. If a file is stale:
- Update it if you can determine the correct current state
- Otherwise, add an entry to `memory/domains/_system/review-queue.md`
  describing what needs human review

### 2. Index Maintenance

For domains with 5+ files and no `_index.md` (marked "NO" in the Index
column), or where `_index.md` is older than the newest file in the
domain, regenerate the index. An `_index.md` should contain:
- Brief summary of the domain's purpose
- List of files with one-line descriptions
- Key entities and cross-references

### 3. Contradiction Detection

Cross-reference information across domain files. Look for:
- Dates or deadlines that conflict between files
- Statements that contradict each other
- Outdated references to completed or cancelled items

If you find contradictions you can resolve, fix them. If not, add to
the review queue.

### 4. Gap Analysis

Identify missing information that could reasonably be filled:
- Domains with very few files relative to their scope
- Files that reference other documents that don't exist
- Key topics mentioned in domain files but never elaborated

### 5. Regression Check

Review these ledger patterns for issues:

{{ ledger_patterns }}

Look for:
- Actions that are always blocked (might need trigger adjustments)
- Actions that are never executed (might be misconfigured)
- Patterns suggesting the user's workflow has changed

---

## Workspace State

{{ domain_audit_table }}

---

## Completion Rules

1. Write a summary of all changes you made to
   `memory/domains/_system/last-review-summary.md`
2. Do NOT tag completion until you are satisfied with your changes
3. If you modified any config file, validation must pass with zero errors
4. Signal completion with:
   `<saf-action id="knowledge_audit" status="sent"/>`
