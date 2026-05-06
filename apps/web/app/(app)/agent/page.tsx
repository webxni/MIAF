"use client";

import { FormEvent, useMemo, useState } from "react";

import { SectionCard } from "../../_components/cards";
import {
  ApiRequestError,
  chatWithAgent,
  type AgentToolCall,
  type ConversationMessage,
  type PendingConfirmation,
} from "../../_lib/api";
import { brand } from "../../_lib/brand";

const EXAMPLE_PROMPTS = [
  "Explain the balance sheet.",
  "Compare my personal and business cash flow.",
  "Gasté $35 en gasolina personal.",
];

type ChatMessage = {
  role: "user" | "agent";
  text: string;
  toolCalls?: AgentToolCall[];
  confirmations?: PendingConfirmation[];
  disclaimers?: string[];
};

export default function AgentPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const hasMessages = messages.length > 0;

  function buildHistory(currentMessages: ChatMessage[]): ConversationMessage[] {
    const history: ConversationMessage[] = [];
    for (const msg of currentMessages) {
      if (msg.role === "user") {
        history.push({ role: "user", content: msg.text });
      } else if (msg.role === "agent" && msg.text) {
        history.push({ role: "assistant", content: msg.text });
      }
    }
    return history.slice(-20);
  }

  const pendingCount = useMemo(
    () => messages.reduce((count, message) => count + (message.confirmations?.length ?? 0), 0),
    [messages],
  );

  async function submitMessage(payloadMessage: string) {
    if (!payloadMessage.trim()) return;
    const userText = payloadMessage.trim();
    setSubmitting(true);
    setError(null);
    let history: ConversationMessage[] = [];
    setMessages((current) => {
      history = buildHistory(current);
      return [...current, { role: "user", text: userText }];
    });
    setInput("");
    try {
      const response = await chatWithAgent({ message: userText, conversation_history: history });
      setMessages((current) => [
        ...current,
        {
          role: "agent",
          text: response.message,
          toolCalls: response.tool_calls,
          confirmations: response.pending_confirmations,
          disclaimers: response.disclaimers,
        },
      ]);
    } catch (err) {
      setError(formatError(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await submitMessage(input);
  }

  async function handleConfirm(target: PendingConfirmation) {
    setSubmitting(true);
    setError(null);
    let history: ConversationMessage[] = [];
    setMessages((current) => {
      history = buildHistory(current);
      return [...current, { role: "user", text: "Confirm." }];
    });
    try {
      const response = await chatWithAgent({
        message: "Confirm.",
        confirmations: [{ tool_name: target.tool_name, arguments: target.arguments }],
        conversation_history: history,
      });
      setMessages((current) =>
        current.map((message) =>
          message.confirmations?.length
            ? {
                ...message,
                confirmations: message.confirmations.filter(
                  (confirmation) =>
                    !sameConfirmation(confirmation, target),
                ),
              }
            : message,
        ).concat({
          role: "agent",
          text: response.message,
          toolCalls: response.tool_calls,
          confirmations: response.pending_confirmations,
          disclaimers: response.disclaimers,
        }),
      );
    } catch (err) {
      setError(formatError(err));
    } finally {
      setSubmitting(false);
    }
  }

  function handleDecline(target: PendingConfirmation) {
    setMessages((current) =>
      current
        .map((message) =>
          message.confirmations?.length
            ? {
                ...message,
                confirmations: message.confirmations.filter(
                  (confirmation) => !sameConfirmation(confirmation, target),
                ),
              }
            : message,
        )
        .concat({
          role: "agent",
          text: `Confirmation declined for ${target.tool_name}. No action was sent.`,
        }),
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.25em] text-[var(--accent)]">Agent</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight">Agent chat</h1>
        <p className="mt-3 max-w-3xl text-sm text-[var(--muted)]">
          {brand.agentIntro} Usa el proveedor de IA configurado en Settings y vuelve a heurísticas
          deterministas si no hay una clave API disponible.
        </p>
      </div>

      {error ? (
        <div className="rounded-2xl border border-[var(--danger-line)] bg-[var(--danger-bg)] px-5 py-4 text-sm text-[var(--danger-ink)]">
          {error}
        </div>
      ) : null}

      <SectionCard
        title="Thread"
        description={
          pendingCount > 0
            ? `${pendingCount} sensitive action${pendingCount === 1 ? "" : "s"} waiting for confirmation.`
            : "Review tool planning and confirm only the actions you want executed."
        }
      >
        {hasMessages ? (
          <div className="space-y-4">
            {messages.map((message, index) => (
              <article
                key={`${message.role}-${index}-${message.text}`}
                className={`rounded-2xl border px-4 py-4 ${
                  message.role === "user"
                    ? "ml-auto max-w-3xl border-[var(--accent)] bg-[var(--panel)]"
                    : "max-w-4xl border-[var(--line)] bg-[var(--surface)]"
                }`}
              >
                <div className="flex items-center justify-between gap-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--muted)]">
                    {message.role === "user" ? "You" : "Agent"}
                  </p>
                  {message.toolCalls?.length ? (
                    <span className="text-xs text-[var(--muted)]">
                      {message.toolCalls.length} tool call{message.toolCalls.length === 1 ? "" : "s"}
                    </span>
                  ) : null}
                </div>
                <p className="mt-2 whitespace-pre-wrap text-sm leading-6">{message.text}</p>

                {message.disclaimers?.length ? (
                  <div className="mt-3 rounded-2xl border border-[var(--line)] bg-[var(--panel)] px-4 py-3 text-sm text-[var(--muted)]">
                    {message.disclaimers.map((disclaimer) => (
                      <p key={disclaimer}>{disclaimer}</p>
                    ))}
                  </div>
                ) : null}

                {message.toolCalls?.length ? (
                  <div className="mt-4 grid gap-3">
                    {message.toolCalls.map((call, callIndex) => (
                      <div
                        key={`${call.tool_name}-${callIndex}`}
                        className="rounded-2xl border border-[var(--line)] bg-[var(--panel)] p-3"
                      >
                        <div className="flex items-center justify-between gap-3">
                          <p className="text-sm font-semibold">{call.tool_name}</p>
                          <span className="text-xs uppercase tracking-[0.15em] text-[var(--muted)]">
                            {call.status}
                          </span>
                        </div>
                        <pre className="mt-2 overflow-x-auto rounded-xl bg-[var(--surface)] p-3 text-xs text-[var(--muted)]">
                          {JSON.stringify(call.result ?? call.arguments, null, 2)}
                        </pre>
                        {call.error ? (
                          <p className="mt-2 text-xs text-[var(--danger-ink)]">{call.error}</p>
                        ) : null}
                      </div>
                    ))}
                  </div>
                ) : null}

                {message.confirmations?.length ? (
                  <div className="mt-4 grid gap-3">
                    {message.confirmations.map((confirmation, confirmationIndex) => (
                      <div
                        key={`${confirmation.tool_name}-${confirmationIndex}`}
                        className="rounded-2xl border border-[var(--line)] bg-[var(--panel)] p-4"
                      >
                        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                          <div>
                            <p className="text-sm font-semibold">{confirmation.tool_name}</p>
                            <p className="mt-1 text-sm text-[var(--muted)]">{confirmation.reason}</p>
                          </div>
                          <div className="flex gap-2">
                            <button
                              type="button"
                              onClick={() => handleConfirm(confirmation)}
                              disabled={submitting}
                              className="rounded-xl bg-[var(--accent)] px-3 py-2 text-sm font-medium text-[var(--accent-ink)] transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
                            >
                              Confirm
                            </button>
                            <button
                              type="button"
                              onClick={() => handleDecline(confirmation)}
                              disabled={submitting}
                              className="rounded-xl border border-[var(--line)] px-3 py-2 text-sm text-[var(--muted)] transition hover:bg-[var(--surface)] hover:text-[var(--ink)] disabled:cursor-not-allowed disabled:opacity-60"
                            >
                              Decline
                            </button>
                          </div>
                        </div>
                        <pre className="mt-3 overflow-x-auto rounded-xl bg-[var(--surface)] p-3 text-xs text-[var(--muted)]">
                          {JSON.stringify(confirmation.arguments, null, 2)}
                        </pre>
                      </div>
                    ))}
                  </div>
                ) : null}
              </article>
            ))}
          </div>
        ) : (
          <div className="rounded-2xl border border-dashed border-[var(--line)] bg-[var(--surface)] px-5 py-8">
            <p className="text-sm text-[var(--muted)]">
              {brand.agentIntro} Empieza con una pregunta o una acción. Verás borradores, planes de
              herramientas y confirmaciones antes de ejecutar pasos sensibles.
            </p>
            <div className="mt-4 flex flex-wrap gap-3">
              {EXAMPLE_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => setInput(prompt)}
                  className="rounded-full border border-[var(--line)] bg-[var(--panel)] px-4 py-2 text-sm transition hover:border-[var(--accent)] hover:text-[var(--accent)]"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        )}
      </SectionCard>

      <SectionCard title="Compose" description="The backend owns planning, policy checks, and confirmation requirements.">
        <form className="space-y-3" onSubmit={handleSubmit}>
          <textarea
            className="min-h-[8rem] w-full rounded-2xl border border-[var(--line)] bg-[var(--surface)] px-4 py-3 text-sm outline-none transition focus:border-[var(--accent)]"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Ask the agent to explain a report, compare contexts, or draft an action…"
            maxLength={4000}
            disabled={submitting}
          />
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs text-[var(--muted)]">{input.length}/4000</p>
            <button
              type="submit"
              disabled={submitting || !input.trim()}
              className="rounded-xl bg-[var(--accent)] px-4 py-2 text-sm font-medium text-[var(--accent-ink)] transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {submitting ? "Sending…" : "Send"}
            </button>
          </div>
        </form>
      </SectionCard>
    </div>
  );
}

function sameConfirmation(left: PendingConfirmation, right: PendingConfirmation) {
  return (
    left.tool_name === right.tool_name &&
    JSON.stringify(left.arguments) === JSON.stringify(right.arguments)
  );
}

function formatError(error: unknown) {
  if (error instanceof ApiRequestError && error.status === 429 && error.code === "agent_rate_limited") {
    return "Slow down a bit.";
  }
  return error instanceof Error ? error.message : "Agent request failed";
}
