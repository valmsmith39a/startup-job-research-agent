import type Anthropic from "@anthropic-ai/sdk";
import { anthropic, MODEL } from "./client";
import { systemPrompt } from "./prompt";
import { tools } from "./tools";

type MessageParam = Anthropic.Beta.BetaMessageParam;

export type AgentEvent =
  | { type: "text"; delta: string }
  | { type: "search"; query: string }
  | { type: "sources"; sources: { title: string; url: string }[] }
  | { type: "notice"; message: string }
  | { type: "error"; message: string }
  // The assistant messages to append to the history, unchanged, before the next turn.
  | { type: "done"; messages: MessageParam[] };

// A server-tool turn can pause; each resend continues it. Cap the resends.
const MAX_CONTINUATIONS = 5;

export async function* runAgent(history: MessageParam[]): AsyncGenerator<AgentEvent> {
  const messages = [...history];
  const appended: MessageParam[] = [];

  for (let i = 0; i <= MAX_CONTINUATIONS; i++) {
    const stream = anthropic.beta.messages.stream({
      model: MODEL,
      max_tokens: 64000,
      system: systemPrompt(),
      thinking: { type: "adaptive" },
      output_config: { effort: "medium" },
      fallbacks: "default",
      betas: ["server-side-fallback-2026-07-01"],
      tools,
      messages,
    });

    for await (const event of stream) {
      if (event.type === "content_block_delta" && event.delta.type === "text_delta") {
        yield { type: "text", delta: event.delta.text };
      } else if (event.type === "content_block_stop") {
        const block = stream.currentMessage?.content[event.index];
        if (block?.type === "server_tool_use" && block.name === "web_search") {
          const query = (block.input as { query?: unknown }).query;
          if (typeof query === "string") yield { type: "search", query };
        } else if (block?.type === "web_search_tool_result" && Array.isArray(block.content)) {
          yield {
            type: "sources",
            sources: block.content.map((r) => ({ title: r.title, url: r.url })),
          };
        }
      }
    }

    const message = await stream.finalMessage();

    if (message.stop_reason === "refusal") {
      yield { type: "error", message: "Claude declined to answer this request." };
      yield { type: "done", messages: [] };
      return;
    }

    const assistant: MessageParam = { role: "assistant", content: message.content };
    messages.push(assistant);
    appended.push(assistant);

    if (message.stop_reason !== "pause_turn") {
      if (message.stop_reason === "max_tokens") {
        yield { type: "notice", message: "The response hit the length limit and was cut off." };
      }
      break;
    }
  }

  yield { type: "done", messages: appended };
}
