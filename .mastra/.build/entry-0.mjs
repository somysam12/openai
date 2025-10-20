import { Mastra } from '@mastra/core';
import { MastraError } from '@mastra/core/error';
import { PinoLogger } from '@mastra/loggers';
import { MastraLogger, LogLevel } from '@mastra/core/logger';
import pino from 'pino';
import { MCPServer } from '@mastra/mcp';
import { Inngest, NonRetriableError } from 'inngest';
import { z } from 'zod';
import * as fs from 'fs';
import * as path from 'path';
import { PostgresStore } from '@mastra/pg';
import { realtimeMiddleware } from '@inngest/realtime';
import { serve, init } from '@mastra/inngest';
import { registerApiRoute as registerApiRoute$1 } from '@mastra/core/server';
import { createOpenAI } from '@ai-sdk/openai';
import { Agent } from '@mastra/core/agent';
import { Memory } from '@mastra/memory';

const sharedPostgresStorage = new PostgresStore({
  connectionString: process.env.DATABASE_URL || "postgresql://localhost:5432/mastra"
});

const inngest = new Inngest(
  process.env.NODE_ENV === "production" ? {
    id: "replit-agent-workflow",
    name: "Replit Agent Workflow System"
  } : {
    id: "mastra",
    baseUrl: "http://localhost:3000",
    isDev: true,
    middleware: [realtimeMiddleware()]
  }
);

const {
  createWorkflow: originalCreateWorkflow,
  createStep} = init(inngest);
function createWorkflow(params) {
  return originalCreateWorkflow({
    ...params,
    retryConfig: {
      attempts: process.env.NODE_ENV === "production" ? 3 : 0,
      ...params.retryConfig ?? {}
    }
  });
}
const inngestFunctions = [];
function registerApiRoute(...args) {
  const [path, options] = args;
  if (path.startsWith("/api/") || typeof options !== "object") {
    return registerApiRoute$1(...args);
  }
  inngestFunctions.push(
    inngest.createFunction(
      {
        id: `api-${path.replace(/^\/+/, "").replaceAll(/\/+/g, "-")}`,
        name: path
      },
      {
        event: `event/api.${path.replace(/^\/+/, "").replaceAll(/\/+/g, ".")}`
      },
      async ({ event, step }) => {
        await step.run("forward request to Mastra", async () => {
          const response = await fetch(`http://localhost:5000${path}`, {
            method: event.data.method,
            headers: event.data.headers,
            body: event.data.body
          });
          if (!response.ok) {
            if (response.status >= 500 && response.status < 600 || response.status == 429 || response.status == 408) {
              throw new Error(
                `Failed to forward request to Mastra: ${response.statusText}`
              );
            } else {
              throw new NonRetriableError(
                `Failed to forward request to Mastra: ${response.statusText}`
              );
            }
          }
        });
      }
    )
  );
  return registerApiRoute$1(...args);
}
function inngestServe({
  mastra,
  inngest: inngest2
}) {
  let serveHost = void 0;
  if (process.env.NODE_ENV === "production") {
    if (process.env.REPLIT_DOMAINS) {
      serveHost = `https://${process.env.REPLIT_DOMAINS.split(",")[0]}`;
    }
  } else {
    serveHost = "http://localhost:5000";
  }
  return serve({
    mastra,
    inngest: inngest2,
    functions: inngestFunctions,
    registerOptions: { serveHost }
  });
}

const openai = createOpenAI({
  baseURL: process.env.OPENAI_BASE_URL || void 0,
  apiKey: process.env.OPENAI_API_KEY
});
const telegramChatAgent = new Agent({
  name: "Telegram Chat Agent",
  instructions: `Arre bhai! Tu ek bindaas aur mast AI chatbot hai jo funny Hinglish style mein baat karta hai! \u{1F604}

PEHLE MESSAGE MEIN (if user hasn't said their language preference):
"Arre namaste dost! \u{1F64F} Main aapka AI buddy hoon! Bataiye, aap kis language mein comfortable ho? Hindi, English, Hinglish, ya koi aur? Jisme aapka mann kare, usi mein baat karte hain! \u{1F60A}"

LANGUAGE RULES:
- Once user tells their preference, REMEMBER IT and use that language for all future messages in this conversation
- Store their preference in your memory and ALWAYS use it
- If they say "Hindi" - speak in pure Hindi
- If they say "English" - speak in English  
- If they say "Hinglish" - use the fun Hinglish mix (default if not specified)
- If they say another language, acknowledge and do your best

YOUR PERSONALITY (use user's preferred language):
- Funny aur entertaining way mein baat karo (in their chosen language)
- Casual, friendly, relatable - jaise ek dost ho
- Use emojis to make conversations lively \u{1F604}\u{1F389}
- Keep responses helpful BUT entertaining
- Be respectful but not boring
- Add humor when appropriate
- Remember previous messages in conversation

RESPONSE STYLE EXAMPLES (Hinglish):
- Instead of "Yes, I can help" \u2192 "Haan bhai, bilkul! Batao kya chahiye? \u{1F60A}"
- Instead of "I don't know" \u2192 "Arre yaar, mujhe iska pata nahi! Par Google kar leta hoon dimaag mein... \u{1F914}"
- Instead of "Thank you" \u2192 "Shukriya boss! Aur kuch chahiye? \u{1F604}"

YOUR ROLE:
- Engage in natural, helpful, FUN conversations
- Answer questions to the best of your ability
- Be polite but with personality
- Keep it light and enjoyable
- Remember what user said before

Keep responses SHORT and SWEET - nobody likes long boring paragraphs! Use user's preferred language consistently.`,
  model: openai.responses("gpt-4o"),
  memory: new Memory({
    options: {
      threads: {
        generateTitle: true
      },
      lastMessages: 10
    },
    storage: sharedPostgresStorage
  })
});

const useAgentStep = createStep({
  id: "use-agent",
  description: "Process user message with AI agent",
  inputSchema: z.object({
    message: z.string(),
    threadId: z.string(),
    chatId: z.number()
  }),
  outputSchema: z.object({
    response: z.string(),
    chatId: z.number()
  }),
  execute: async ({ inputData, mastra }) => {
    const logger = mastra?.getLogger();
    logger?.info("\u{1F916} [Use Agent Step] Starting agent generation", {
      message: inputData.message,
      threadId: inputData.threadId
    });
    const { text } = await telegramChatAgent.generate(
      [{ role: "user", content: inputData.message }],
      {
        resourceId: "telegram-bot",
        threadId: inputData.threadId,
        maxSteps: 5
      }
    );
    logger?.info("\u2705 [Use Agent Step] Agent response generated", {
      responseLength: text.length
    });
    return {
      response: text,
      chatId: inputData.chatId
    };
  }
});
const sendTelegramReplyStep = createStep({
  id: "send-telegram-reply",
  description: "Send agent's response back to Telegram",
  inputSchema: z.object({
    response: z.string(),
    chatId: z.number()
  }),
  outputSchema: z.object({
    sent: z.boolean()
  }),
  execute: async ({ inputData, mastra }) => {
    const logger = mastra?.getLogger();
    logger?.info("\u{1F4E4} [Send Reply Step] Sending message to Telegram", {
      chatId: inputData.chatId,
      responseLength: inputData.response.length
    });
    const telegramToken = process.env.TELEGRAM_BOT_TOKEN;
    if (!telegramToken) {
      logger?.warn("\u26A0\uFE0F [Send Reply Step] TELEGRAM_BOT_TOKEN not found, skipping send");
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
            text: inputData.response
          })
        }
      );
      if (!response.ok) {
        const errorText = await response.text();
        logger?.error("\u274C [Send Reply Step] Failed to send message", {
          status: response.status,
          error: errorText
        });
        return { sent: false };
      }
      logger?.info("\u2705 [Send Reply Step] Message sent successfully");
      return { sent: true };
    } catch (error) {
      logger?.error("\u274C [Send Reply Step] Error sending message", { error });
      return { sent: false };
    }
  }
});
const telegramChatWorkflow = createWorkflow({
  id: "telegram-chat-workflow",
  description: "Handle Telegram messages with AI agent",
  inputSchema: z.object({
    message: z.string(),
    threadId: z.string(),
    chatId: z.number()
  }),
  outputSchema: z.object({
    sent: z.boolean()
  })
}).then(useAgentStep).then(sendTelegramReplyStep).commit();

if (!process.env.TELEGRAM_BOT_TOKEN) {
  console.warn(
    "Trying to initialize Telegram triggers without TELEGRAM_BOT_TOKEN. Can you confirm that the Telegram integration is configured correctly?"
  );
}
function registerTelegramTrigger({
  triggerType,
  handler
}) {
  return [
    registerApiRoute("/webhooks/telegram/action", {
      method: "POST",
      handler: async (c) => {
        const mastra = c.get("mastra");
        const logger = mastra.getLogger();
        try {
          const payload = await c.req.json();
          logger?.info("\u{1F4DD} [Telegram] payload", payload);
          await handler(mastra, {
            type: triggerType,
            params: {
              userName: payload.message.from.username,
              message: payload.message.text
            },
            payload
          });
          return c.text("OK", 200);
        } catch (error) {
          logger?.error("Error handling Telegram webhook:", error);
          return c.text("Internal Server Error", 500);
        }
      }
    })
  ];
}

const PROJECT_ROOT = "/home/runner/workspace";
class ProductionPinoLogger extends MastraLogger {
  logger;
  constructor(options = {}) {
    super(options);
    this.logger = pino({
      name: options.name || "app",
      level: options.level || LogLevel.INFO,
      base: {},
      formatters: {
        level: (label, _number) => ({
          level: label
        })
      },
      timestamp: () => `,"time":"${new Date(Date.now()).toISOString()}"`
    });
  }
  debug(message, args = {}) {
    this.logger.debug(args, message);
  }
  info(message, args = {}) {
    this.logger.info(args, message);
  }
  warn(message, args = {}) {
    this.logger.warn(args, message);
  }
  error(message, args = {}) {
    this.logger.error(args, message);
  }
}
const mastra = new Mastra({
  storage: sharedPostgresStorage,
  // Register your workflows here
  workflows: {
    telegramChatWorkflow
  },
  // Register your agents here
  agents: {
    telegramChatAgent
  },
  mcpServers: {
    allTools: new MCPServer({
      name: "allTools",
      version: "1.0.0",
      tools: {}
    })
  },
  bundler: {
    // A few dependencies are not properly picked up by
    // the bundler if they are not added directly to the
    // entrypoint.
    externals: ["@slack/web-api", "inngest", "inngest/hono", "hono", "hono/streaming"],
    // sourcemaps are good for debugging.
    sourcemap: true
  },
  server: {
    host: "0.0.0.0",
    port: 5e3,
    middleware: [async (c, next) => {
      const mastra2 = c.get("mastra");
      const logger = mastra2?.getLogger();
      logger?.debug("[Request]", {
        method: c.req.method,
        url: c.req.url
      });
      try {
        await next();
      } catch (error) {
        logger?.error("[Response]", {
          method: c.req.method,
          url: c.req.url,
          error
        });
        if (error instanceof MastraError) {
          if (error.id === "AGENT_MEMORY_MISSING_RESOURCE_ID") {
            throw new NonRetriableError(error.message, {
              cause: error
            });
          }
        } else if (error instanceof z.ZodError) {
          throw new NonRetriableError(error.message, {
            cause: error
          });
        }
        throw error;
      }
    }],
    apiRoutes: [
      // Serve index.html at root
      {
        path: "/",
        method: "GET",
        createHandler: async () => async (c) => {
          try {
            const publicPath = path.join(PROJECT_ROOT, "public", "index.html");
            const html = fs.readFileSync(publicPath, "utf-8");
            return c.html(html, 200, {
              "Cache-Control": "no-cache"
            });
          } catch (error) {
            return c.text("Error loading page: " + String(error), 500);
          }
        }
      },
      // Serve CSS files
      {
        path: "/chat.css",
        method: "GET",
        createHandler: async () => async (c) => {
          try {
            const cssPath = path.join(PROJECT_ROOT, "public", "chat.css");
            const css = fs.readFileSync(cssPath, "utf-8");
            return c.text(css, 200, {
              "Content-Type": "text/css",
              "Cache-Control": "no-cache"
            });
          } catch (error) {
            return c.text("CSS not found", 404);
          }
        }
      },
      // Serve JS files
      {
        path: "/chat.js",
        method: "GET",
        createHandler: async () => async (c) => {
          try {
            const jsPath = path.join(PROJECT_ROOT, "public", "chat.js");
            const js = fs.readFileSync(jsPath, "utf-8");
            return c.text(js, 200, {
              "Content-Type": "application/javascript",
              "Cache-Control": "no-cache"
            });
          } catch (error) {
            return c.text("JS not found", 404);
          }
        }
      },
      // Web chat API endpoint
      {
        path: "/api/chat",
        method: "POST",
        createHandler: async ({
          mastra: mastra2
        }) => {
          return async (c) => {
            const logger = mastra2.getLogger();
            try {
              const {
                message,
                sessionId
              } = await c.req.json();
              if (!message || !sessionId) {
                return c.json({
                  error: "Message and sessionId required"
                }, 400);
              }
              logger?.info("\u{1F4AC} [Web Chat] Received message", {
                sessionId,
                messageLength: message.length
              });
              const {
                text
              } = await telegramChatAgent.generate([{
                role: "user",
                content: message
              }], {
                resourceId: "web-bot",
                threadId: sessionId,
                maxSteps: 5
              });
              logger?.info("\u2705 [Web Chat] Response generated", {
                sessionId,
                responseLength: text.length
              });
              return c.json({
                response: text
              });
            } catch (error) {
              logger?.error("\u274C [Web Chat] Error", {
                error
              });
              return c.json({
                error: "Failed to process message"
              }, 500);
            }
          };
        }
      },
      // This API route is used to register the Mastra workflow (inngest function) on the inngest server
      {
        path: "/api/inngest",
        method: "ALL",
        createHandler: async ({
          mastra: mastra2
        }) => inngestServe({
          mastra: mastra2,
          inngest
        })
        // The inngestServe function integrates Mastra workflows with Inngest by:
        // 1. Creating Inngest functions for each workflow with unique IDs (workflow.${workflowId})
        // 2. Setting up event handlers that:
        //    - Generate unique run IDs for each workflow execution
        //    - Create an InngestExecutionEngine to manage step execution
        //    - Handle workflow state persistence and real-time updates
        // 3. Establishing a publish-subscribe system for real-time monitoring
        //    through the workflow:${workflowId}:${runId} channel
      },
      ...registerTelegramTrigger({
        triggerType: "telegram/message",
        handler: async (mastra2, triggerInfo) => {
          const logger = mastra2.getLogger();
          logger?.info("\u{1F4DD} [Telegram Trigger] Received message", {
            userName: triggerInfo.params.userName,
            message: triggerInfo.params.message,
            chatId: triggerInfo.payload.message.chat.id
          });
          const run = await mastra2.getWorkflow("telegramChatWorkflow").createRunAsync();
          await run.start({
            inputData: {
              message: triggerInfo.params.message,
              threadId: `telegram/${triggerInfo.payload.message.chat.id}`,
              chatId: triggerInfo.payload.message.chat.id
            }
          });
        }
      })
    ]
  },
  logger: process.env.NODE_ENV === "production" ? new ProductionPinoLogger({
    name: "Mastra",
    level: "info"
  }) : new PinoLogger({
    name: "Mastra",
    level: "info"
  })
});
if (Object.keys(mastra.getWorkflows()).length > 1) {
  throw new Error("More than 1 workflows found. Currently, more than 1 workflows are not supported in the UI, since doing so will cause app state to be inconsistent.");
}
if (Object.keys(mastra.getAgents()).length > 1) {
  throw new Error("More than 1 agents found. Currently, more than 1 agents are not supported in the UI, since doing so will cause app state to be inconsistent.");
}

export { mastra };
