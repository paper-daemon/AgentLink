---
name: choice-deck
description: Present three tappable, model-authored next-step choices when a user needs a branch, confirmation, or a checkpoint during a long multi-stage workflow.
---

Use the `show_choice_deck` MCP tool when three concrete next steps would help the user.

Rules:
- Always provide exactly three materially different choices.
- You may freely author each card's title, short description, badge, and follow-up prompt.
- The follow-up prompt should contain enough context to continue naturally when the card is tapped.
- For long multi-stage work, a deck may be used at a natural checkpoint so the user can explicitly continue in a fresh turn.
- One choice may be a developer-oriented path such as "verify", "inspect logs", "run tests", or "continue with tools" when that is genuinely useful.
- Do not describe a card tap as extending the same model execution. It starts a follow-up conversational turn.
- Do not use the deck when one obvious next action should simply be performed.
