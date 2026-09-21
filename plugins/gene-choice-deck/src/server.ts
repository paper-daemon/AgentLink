import express from "express";
import { randomUUID } from "node:crypto";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { isInitializeRequest } from "@modelcontextprotocol/sdk/types.js";
import { z } from "zod/v3";

const PORT = Number(process.env.PORT || 3000);
const TEMPLATE_URI = "ui://gene-choice-deck/v1.html";

const choiceSchema = z.object({
  id: z.string().min(1).max(64),
  title: z.string().min(1).max(72),
  description: z.string().max(180).optional(),
  badge: z.string().max(24).optional(),
  prompt: z.string().min(1).max(4000),
});

const widgetHtml = String.raw`
<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<style>
  :root { color-scheme: light dark; font-family: ui-sans-serif, system-ui, -apple-system, sans-serif; }
  body { margin: 0; padding: 10px; background: transparent; }
  .wrap { display: grid; gap: 10px; }
  .head { display: grid; gap: 3px; }
  h3 { margin: 0; font-size: 15px; line-height: 1.3; }
  .sub { opacity: .68; font-size: 12px; line-height: 1.45; }
  .cards { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 8px; }
  button {
    appearance: none; border: 1px solid color-mix(in srgb, currentColor 18%, transparent);
    border-radius: 14px; padding: 12px; text-align: left; background: color-mix(in srgb, currentColor 5%, transparent);
    color: inherit; cursor: pointer; min-height: 92px;
  }
  button:hover { background: color-mix(in srgb, currentColor 9%, transparent); }
  button:disabled { cursor: default; opacity: .55; }
  button.selected { outline: 2px solid color-mix(in srgb, currentColor 45%, transparent); }
  .badge { font-size: 10px; opacity: .7; margin-bottom: 6px; }
  .title { font-size: 13px; font-weight: 700; line-height: 1.3; }
  .desc { margin-top: 5px; font-size: 11px; opacity: .7; line-height: 1.4; }
  .status { min-height: 16px; font-size: 11px; opacity: .7; }
  @media (max-width: 540px) {
    .cards { grid-template-columns: 1fr; }
    button { min-height: 72px; }
  }
</style>
</head>
<body>
<div class="wrap">
  <div class="head">
    <h3 id="heading">次どうする？</h3>
    <div class="sub" id="subheading"></div>
  </div>
  <div class="cards" id="cards"></div>
  <div class="status" id="status"></div>
</div>
<script>
(() => {
  const cardsEl = document.getElementById("cards");
  const headingEl = document.getElementById("heading");
  const subheadingEl = document.getElementById("subheading");
  const statusEl = document.getElementById("status");
  let current = null;
  let locked = false;

  function readInitial() {
    const out = window.openai && window.openai.toolOutput;
    if (out && out.choices) render(out);
  }

  function render(data) {
    if (!data || !Array.isArray(data.choices)) return;
    current = data;
    headingEl.textContent = data.heading || "次どうする？";
    subheadingEl.textContent = data.subheading || "";
    cardsEl.innerHTML = "";
    data.choices.slice(0, 3).forEach((choice) => {
      const btn = document.createElement("button");
      btn.dataset.id = choice.id;
      btn.innerHTML =
        (choice.badge ? '<div class="badge"></div>' : "") +
        '<div class="title"></div>' +
        (choice.description ? '<div class="desc"></div>' : "");
      if (choice.badge) btn.querySelector(".badge").textContent = choice.badge;
      btn.querySelector(".title").textContent = choice.title;
      if (choice.description) btn.querySelector(".desc").textContent = choice.description;
      btn.onclick = () => choose(choice, btn);
      cardsEl.appendChild(btn);
    });
  }

  async function choose(choice, btn) {
    if (locked) return;
    locked = true;
    [...cardsEl.querySelectorAll("button")].forEach((b) => b.disabled = true);
    btn.classList.add("selected");
    statusEl.textContent = "選択を送信中…";

    try {
      if (window.openai && window.openai.setWidgetState) {
        window.openai.setWidgetState({
          selectedChoiceId: choice.id,
          selectedChoiceTitle: choice.title,
          selectedAt: new Date().toISOString()
        });
      }

      if (!window.openai || !window.openai.sendFollowUpMessage) {
        throw new Error("This host does not expose sendFollowUpMessage.");
      }

      await window.openai.sendFollowUpMessage({
        prompt: choice.prompt,
        scrollToBottom: true
      });
      statusEl.textContent = "送信したよ ✓";
    } catch (err) {
      locked = false;
      [...cardsEl.querySelectorAll("button")].forEach((b) => b.disabled = false);
      statusEl.textContent = "送信できなかった。もう一度押してみて。";
    }
  }

  window.addEventListener("message", (event) => {
    if (event.source !== window.parent) return;
    const msg = event.data;
    if (!msg || msg.jsonrpc !== "2.0") return;
    if (msg.method === "ui/notifications/tool-result") {
      render(msg.params && msg.params.structuredContent);
    }
  }, { passive: true });

  readInitial();
})();
</script>
</body>
</html>
`.trim();

function buildServer() {
  const server = new McpServer(
    { name: "gene-choice-deck", version: "0.1.0" },
    {
      capabilities: { tools: {}, resources: {} },
      instructions:
        "Render a three-choice deck when the user benefits from choosing the next direction. " +
        "The model authors all three labels, descriptions, badges, and follow-up prompts. " +
        "For long multi-stage work, use the deck at natural checkpoints so the user can explicitly continue in a fresh turn. " +
        "Do not claim the deck extends a single model execution."
    }
  );

  server.registerResource("gene-choice-deck-widget", TEMPLATE_URI, {}, async () => ({
    contents: [{
      uri: TEMPLATE_URI,
      mimeType: "text/html;profile=mcp-app",
      text: widgetHtml,
      _meta: { ui: { prefersBorder: true } }
    }]
  }));

  server.registerTool(
    "show_choice_deck",
    {
      title: "Show Gene choice deck",
      description:
        "Show exactly three model-authored choices. Use when the user needs a decision, a branching workflow, " +
        "or an explicit checkpoint to continue a long task. Each prompt is posted back to ChatGPT when tapped.",
      inputSchema: {
        heading: z.string().max(100).optional(),
        subheading: z.string().max(240).optional(),
        choices: z.array(choiceSchema).length(3)
      },
      outputSchema: {
        heading: z.string().optional(),
        subheading: z.string().optional(),
        choices: z.array(choiceSchema).length(3)
      },
      annotations: {
        readOnlyHint: true,
        openWorldHint: false,
        destructiveHint: false
      },
      _meta: {
        ui: { resourceUri: TEMPLATE_URI },
        "openai/outputTemplate": TEMPLATE_URI,
        "openai/toolInvocation/invoking": "3つの選択肢を作っています",
        "openai/toolInvocation/invoked": "選択肢を用意しました"
      }
    },
    async ({ heading, subheading, choices }) => ({
      structuredContent: { heading, subheading, choices },
      content: [{
        type: "text",
        text: "Displayed a three-choice deck. Tapping a card posts that card's follow-up prompt into the conversation."
      }]
    })
  );

  return server;
}

type SessionEntry = {
  transport: StreamableHTTPServerTransport;
  server: McpServer;
};

const sessions = new Map<string, SessionEntry>();
const app = express();
app.use(express.json({ limit: "256kb" }));

app.get("/health", (_req, res) => {
  res.json({ ok: true, service: "gene-choice-deck", sessions: sessions.size });
});

app.all("/mcp", async (req, res) => {
  try {
    const rawSession = req.headers["mcp-session-id"];
    const sessionId = Array.isArray(rawSession) ? rawSession[0] : rawSession;

    let entry = sessionId ? sessions.get(sessionId) : undefined;

    if (!entry) {
      if (req.method !== "POST" || !isInitializeRequest(req.body)) {
        res.status(400).json({
          jsonrpc: "2.0",
          id: null,
          error: { code: -32000, message: "No valid MCP session. Initialize first." }
        });
        return;
      }

      const server = buildServer();
      let transport!: StreamableHTTPServerTransport;
      transport = new StreamableHTTPServerTransport({
        sessionIdGenerator: () => randomUUID(),
        onsessioninitialized: (id) => {
          sessions.set(id, { server, transport });
        }
      });
      transport.onclose = () => {
        if (transport.sessionId) sessions.delete(transport.sessionId);
      };
      await server.connect(transport);
      entry = { server, transport };
    }

    await entry.transport.handleRequest(req, res, req.body);
  } catch (error) {
    console.error("MCP request failed", error);
    if (!res.headersSent) {
      res.status(500).json({
        jsonrpc: "2.0",
        id: null,
        error: { code: -32603, message: "Internal server error" }
      });
    }
  }
});

app.listen(PORT, "0.0.0.0", () => {
  console.log(`Gene Choice Deck listening on :${PORT}`);
});
