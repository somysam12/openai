import { createOpenAI } from "@ai-sdk/openai";
import { Agent } from "@mastra/core/agent";
import { Memory } from "@mastra/memory";
import { sharedPostgresStorage } from "../storage";

const openai = createOpenAI({
  baseURL: process.env.OPENAI_BASE_URL || undefined,
  apiKey: process.env.OPENAI_API_KEY,
});

export const telegramChatAgent = new Agent({
  name: "Telegram Chat Agent",
  instructions: `You are a helpful and friendly AI assistant chatting with users on Telegram.

Your role is to:
- Engage in natural, helpful conversations
- Answer questions to the best of your ability
- Be polite, friendly, and respectful
- Provide clear and concise responses
- Remember previous messages in the conversation

Keep your responses conversational and appropriate for a messaging platform like Telegram.`,

  model: openai.responses("gpt-4o"),

  memory: new Memory({
    options: {
      threads: {
        generateTitle: true,
      },
      lastMessages: 10,
    },
    storage: sharedPostgresStorage,
  }),
});
