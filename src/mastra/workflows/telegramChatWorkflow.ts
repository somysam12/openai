import { createStep, createWorkflow } from "../inngest";
import { z } from "zod";
import { telegramChatAgent } from "../agents/telegramChatAgent";

const useAgentStep = createStep({
  id: "use-agent",
  description: "Process user message with AI agent",
  inputSchema: z.object({
    message: z.string(),
    threadId: z.string(),
    chatId: z.number(),
  }),
  outputSchema: z.object({
    response: z.string(),
    chatId: z.number(),
  }),
  execute: async ({ inputData, mastra }) => {
    const logger = mastra?.getLogger();
    logger?.info("🤖 [Use Agent Step] Starting agent generation", {
      message: inputData.message,
      threadId: inputData.threadId,
    });

    const { text } = await telegramChatAgent.generate(
      [{ role: "user", content: inputData.message }],
      {
        resourceId: "telegram-bot",
        threadId: inputData.threadId,
        maxSteps: 5,
      }
    );

    logger?.info("✅ [Use Agent Step] Agent response generated", {
      responseLength: text.length,
    });

    return {
      response: text,
      chatId: inputData.chatId,
    };
  },
});

const sendTelegramReplyStep = createStep({
  id: "send-telegram-reply",
  description: "Send agent's response back to Telegram",
  inputSchema: z.object({
    response: z.string(),
    chatId: z.number(),
  }),
  outputSchema: z.object({
    sent: z.boolean(),
  }),
  execute: async ({ inputData, mastra }) => {
    const logger = mastra?.getLogger();
    logger?.info("📤 [Send Reply Step] Sending message to Telegram", {
      chatId: inputData.chatId,
      responseLength: inputData.response.length,
    });

    const telegramToken = process.env.TELEGRAM_BOT_TOKEN;
    
    if (!telegramToken) {
      logger?.warn("⚠️ [Send Reply Step] TELEGRAM_BOT_TOKEN not found, skipping send");
      return { sent: false };
    }

    try {
      const response = await fetch(
        `https://api.telegram.org/bot${telegramToken}/sendMessage`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            chat_id: inputData.chatId,
            text: inputData.response,
          }),
        }
      );

      if (!response.ok) {
        const errorText = await response.text();
        logger?.error("❌ [Send Reply Step] Failed to send message", {
          status: response.status,
          error: errorText,
        });
        return { sent: false };
      }

      logger?.info("✅ [Send Reply Step] Message sent successfully");
      return { sent: true };
    } catch (error) {
      logger?.error("❌ [Send Reply Step] Error sending message", { error });
      return { sent: false };
    }
  },
});

export const telegramChatWorkflow = createWorkflow({
  id: "telegram-chat-workflow",
  description: "Handle Telegram messages with AI agent",
  inputSchema: z.object({
    message: z.string(),
    threadId: z.string(),
    chatId: z.number(),
  }),
  outputSchema: z.object({
    sent: z.boolean(),
  }),
})
  .then(useAgentStep as any)
  .then(sendTelegramReplyStep as any)
  .commit();
