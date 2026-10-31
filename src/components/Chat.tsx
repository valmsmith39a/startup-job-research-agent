"use client";

import type Anthropic from "@anthropic-ai/sdk";
import { useRef, useState } from "react";
import type { AgentEvent } from "@/lib/agent/run";

type MessageParam = Anthropic.Beta.BetaMessageParam;

type Source = { title: string; url: string };

type Turn = {
  role: "user" | "assistant";
  text: string;
  searches: string[];
  sources: Source[];
  error?: string;
  notice?: string;
};

const EXAMPLES = [
  "Find 3 seed-stage AI infra startups hiring backend engineers",
  "What roles is Anthropic hiring for in San Francisco?",
  "Series A climate tech startups that raised in the last 6 months",
];

export function Chat() {
  // Sent to the API on every turn. Append only: assistant content goes back unchanged.
  const history = useRef<MessageParam[]>([]);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);

  function updateLast(update: (turn: Turn) => Turn) {
    setTurns((prev) => [...prev.slice(0, -1), update(prev[prev.length - 1])]);
  }

  function apply(event: AgentEvent) {
    switch (event.type) {
      case "text":
        updateLast((t) => ({ ...t, text: t.text + event.delta }));
        break;
      case "search":
        updateLast((t) => ({ ...t, searches: [...t.searches, event.query] }));
        break;
      case "sources":
        updateLast((t) => ({
          ...t,
          sources: [...t.sources, ...event.sources.filter((s) => !t.sources.some((x) => x.url === s.url))],
        }));
        break;
      case "notice":
        updateLast((t) => ({ ...t, notice: event.message }));
        break;
      case "error":
        updateLast((t) => ({ ...t, error: event.message }));
        break;
      case "done":
        if (event.messages.length > 0) {
          history.current.push(...event.messages);
        } else {
          // No answer came back, so drop the unanswered user message from the history.
          history.current.pop();
        }
        break;
    }
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }

  async function send(text: string) {
    const prompt = text.trim();
    if (!prompt || busy) return;
    setInput("");
    setBusy(true);
    history.current.push({ role: "user", content: prompt });
    setTurns((prev) => [
      ...prev,
      { role: "user", text: prompt, searches: [], sources: [] },
      { role: "assistant", text: "", searches: [], sources: [] },
    ]);

    let finished = false;
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: history.current }),
      });
      if (!res.ok || !res.body) throw new Error(`Request failed (${res.status})`);

      const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
      let buffer = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += value;
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.trim()) continue;
          const event = JSON.parse(line) as AgentEvent;
          if (event.type === "done") finished = true;
          apply(event);
        }
      }
    } catch (err) {
      updateLast((t) => ({ ...t, error: err instanceof Error ? err.message : "Request failed" }));
    } finally {
      if (!finished) history.current.pop();
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex h-dvh w-full max-w-3xl flex-col px-4">
      <header className="border-b border-black/10 py-4 dark:border-white/15">
        <h1 className="text-lg font-semibold">Startup Job Research</h1>
        <p className="text-sm opacity-60">Ask about startups, funding, and open roles. Answers come from live web search.</p>
      </header>

      <main className="flex-1 space-y-6 overflow-y-auto py-6">
        {turns.length === 0 && (
          <div className="space-y-2">
            {EXAMPLES.map((example) => (
              <button
                key={example}
                onClick={() => send(example)}
                className="block w-full rounded-lg border border-black/10 px-4 py-3 text-left text-sm hover:bg-black/5 dark:border-white/15 dark:hover:bg-white/10"
              >
                {example}
              </button>
            ))}
          </div>
        )}

        {turns.map((turn, i) =>
          turn.role === "user" ? (
            <div key={i} className="ml-auto max-w-[85%] rounded-2xl bg-black/5 px-4 py-2 whitespace-pre-wrap dark:bg-white/10">
              {turn.text}
            </div>
          ) : (
            <div key={i} className="space-y-3">
              {turn.searches.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {turn.searches.map((q, j) => (
                    <span key={j} className="rounded-full border border-black/10 px-3 py-1 text-xs opacity-70 dark:border-white/15">
                      Searched: {q}
                    </span>
                  ))}
                </div>
              )}
              {turn.text ? (
                <div className="leading-relaxed whitespace-pre-wrap">{turn.text}</div>
              ) : (
                busy && i === turns.length - 1 && !turn.error && <div className="text-sm opacity-60">Researching…</div>
              )}
              {turn.notice && <div className="text-sm text-amber-600">{turn.notice}</div>}
              {turn.error && <div className="text-sm text-red-600">{turn.error}</div>}
              {turn.sources.length > 0 && (
                <details className="text-sm">
                  <summary className="cursor-pointer opacity-60">{turn.sources.length} sources</summary>
                  <ul className="mt-2 space-y-1">
                    {turn.sources.map((s) => (
                      <li key={s.url}>
                        <a href={s.url} target="_blank" rel="noreferrer" className="underline underline-offset-2">
                          {s.title || s.url}
                        </a>
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </div>
          ),
        )}
        <div ref={bottom} />
      </main>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
        className="flex gap-2 border-t border-black/10 py-4 dark:border-white/15"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about a startup, a role, or a market…"
          disabled={busy}
          className="flex-1 rounded-lg border border-black/15 bg-transparent px-4 py-2 outline-none focus:border-black/40 dark:border-white/20 dark:focus:border-white/50"
        />
        <button
          type="submit"
          disabled={busy || !input.trim()}
          className="rounded-lg bg-foreground px-4 py-2 text-background disabled:opacity-40"
        >
          Send
        </button>
      </form>
    </div>
  );
}
