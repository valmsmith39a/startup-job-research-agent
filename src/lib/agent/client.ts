import Anthropic from "@anthropic-ai/sdk";

// Reads ANTHROPIC_API_KEY from the environment.
export const anthropic = new Anthropic();

export const MODEL = process.env.ANTHROPIC_MODEL ?? "claude-sonnet-5-5";
