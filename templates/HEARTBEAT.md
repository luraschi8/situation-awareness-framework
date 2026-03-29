# HEARTBEAT.md (Template)

## 🕐 STEP 0: TEMPORAL AWARENESS (MANDATORY)
1. UTC Time: [System Header]
2. Effective Timezone: [user-state.json]
3. Day Phase: [Compute from local time]
4. Day Type: [Workday/Weekend]

## ⚡ ACTION SELECTION
- Check `daily-actions.json` for current date.
- Subtract already-executed actions from the current phase's allowed list.
- Log every new outgoing message in `daily-actions.json`.
