import type Anthropic from "@anthropic-ai/sdk";

// Web search is an Anthropic server tool: it runs on Anthropic's side, so it
// needs no handler here. Add custom tools to this array as the agent grows.
export const tools: Anthropic.Beta.BetaToolUnion[] = [
  { type: "web_search_20260209", name: "web_search", max_uses: 10 },
];
