import Anthropic from "@anthropic-ai/sdk";
import { runAgent, type AgentEvent } from "@/lib/agent/run";

// Research turns with several searches can run for minutes.
export const maxDuration = 300;

export async function POST(request: Request) {
  const body = (await request.json().catch(() => null)) as {
    messages?: Anthropic.Beta.BetaMessageParam[];
  } | null;
  if (!Array.isArray(body?.messages) || body.messages.length === 0) {
    return Response.json({ error: "Expected a non-empty messages array." }, { status: 400 });
  }
  const history = body.messages;

  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      const send = (event: AgentEvent) =>
        controller.enqueue(encoder.encode(JSON.stringify(event) + "\n"));
      try {
        for await (const event of runAgent(history)) send(event);
      } catch (err) {
        console.error(err);
        const message =
          err instanceof Anthropic.RateLimitError
            ? "Rate limited by the Claude API. Try again in a moment."
            : err instanceof Anthropic.APIError
              ? `Claude API error${err.status ? ` (${err.status})` : ""}.`
              : err instanceof Anthropic.AnthropicError && err.message.includes("authentication")
                ? "No Claude API credentials. Set ANTHROPIC_API_KEY."
                : "Something went wrong.";
        send({ type: "error", message });
        send({ type: "done", messages: [] });
      } finally {
        controller.close();
      }
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "application/x-ndjson; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
    },
  });
}
