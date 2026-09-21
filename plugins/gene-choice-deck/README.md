# Gene Choice Deck

Three model-authored choice cards for ChatGPT.

- MCP endpoint: `/mcp`
- Health endpoint: `/health`
- Tool: `show_choice_deck`
- Each card may contain a model-authored title, description, badge, and follow-up prompt.
- Tapping a card uses ChatGPT's `sendFollowUpMessage` bridge to start the next conversational turn.

This is a continuation/checkpoint mechanism. It does not claim to extend one model execution.
