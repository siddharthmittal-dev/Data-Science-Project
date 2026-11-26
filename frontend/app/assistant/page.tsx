"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Modal } from "@/components/Modal";
import Link from "next/link";
import { PatientRecords } from "@/components/PatientRecords";
import { LiveRegion, useToast } from "@/components/Toast";
import {
  ErrorState,
  Skeleton,
  btnPrimary,
  btnSecondary,
} from "@/components/ui";
import {
  type AssistantActionType,
  type AssistantCitation,
  type AssistantReply,
  confirmAssistantAction,
  dismissAssistantAction,
  getGuide,
  getPatientDocument,
  sendAssistantMessage,
  toApiError,
} from "@/lib/api";
import { useLoader } from "@/lib/use-loader";
import { useAuth } from "@/lib/auth";
import { getPatients } from "@/lib/api";

function AssistantPatient({ value, onChange, disabled }: { value: number | undefined; onChange: (id: number | undefined) => void; disabled: boolean }) {
  const { state, retry } = useLoader(getPatients);
  if (state.status === "loading") return <Skeleton lines={1} />;
  if (state.status === "error") return <ErrorState message={state.error.message} onRetry={retry} />;
  return <label className="grid max-w-sm gap-1.5 text-xs text-muted">Patient for this conversation
    <select disabled={disabled} value={value ?? ""} onChange={e => onChange(e.target.value ? Number(e.target.value) : undefined)} className="min-h-11 rounded-xl border border-line bg-panel px-3 text-sm text-ink disabled:opacity-60">
      <option value="">Choose a patient</option>{state.data.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
    </select></label>;
}

const SUGGESTIONS = [
  "Show my appointments",
];

const ACTION_LABEL: Record<AssistantActionType, string> = {
  book: "Book appointment",
  cancel: "Cancel appointment",
  reschedule: "Reschedule appointment",
};

// Card status moves: pending -> confirming -> confirmed | failed;
// pending or failed -> dismissing -> dismissed (or back to its previous status on error).
type CardStatus = "pending" | "confirming" | "confirmed" | "failed" | "dismissing" | "dismissed";

interface ActionCard {
  actionId: number;
  type: AssistantActionType;
  summary: string;
  status: CardStatus;
  error: string | null;
}

type ChatMessage =
  | { id: number; role: "user"; text: string }
  | {
      id: number;
      role: "assistant";
      text: string;
      citations: AssistantCitation[];
      card: ActionCard | null;
      notice?: string | null;
    };

interface FailedSend {
  text: string;
  message: string;
  context: "auto" | "documents" | "insights";
}

const chipClass =
  "inline-flex min-h-11 items-center rounded-full border border-line px-4 text-left text-xs text-muted transition hover:bg-panel hover:text-ink disabled:cursor-not-allowed disabled:opacity-40";

export default function AssistantPage() {
  const auth = useAuth();
  const [patientId, setPatientId] = useState<number>();
  const [documentId, setDocumentId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [failed, setFailed] = useState<FailedSend | null>(null);
  const [openGuide, setOpenGuide] = useState<AssistantCitation | null>(null);
  const { message: toast, show: showToast } = useToast();
  const idRef = useRef(0);
  const listRef = useRef<HTMLDivElement>(null);
  const inFlight = useRef(new Set<number>());
  const sendingRef = useRef(false);
  const isPatient = auth.state.status === "authed" && auth.state.user.role === "patient";
  const isAdmin = auth.state.status === "authed" && auth.state.user.role === "admin";

  function changeDocument(id: string | null) {
    if (sendingRef.current || inFlight.current.size > 0 || id === documentId) return;
    for (const message of messages) {
      if (message.role === "assistant" && message.card?.status === "pending") {
        void dismissAssistantAction(message.card.actionId).catch(() => {});
      }
    }
    setDocumentId(id);
    setMessages([]);
    setInput("");
    setFailed(null);
    setOpenGuide(null);
  }

  function changePatient(id: number | undefined) {
    if (id === patientId || uploading || sendingRef.current || inFlight.current.size > 0) return;
    // Clear the old context immediately, even if dismissing its server proposal fails.
    for (const message of messages) {
      if (message.role === "assistant" && message.card?.status === "pending") {
        void dismissAssistantAction(message.card.actionId).catch(() => {});
      }
    }
    setPatientId(id);
    setDocumentId(null);
    setMessages([]);
    setInput("");
    setFailed(null);
    setOpenGuide(null);
    showToast("Patient changed. Previous conversation cleared.");
  }

  function nextId() {
    idRef.current += 1;
    return idRef.current;
  }

  useEffect(() => {
    const list = listRef.current;
    if (list) list.scrollTop = list.scrollHeight;
  }, [messages.length, sending, failed]);

  async function send(text: string, echo: boolean, context: "auto" | "documents" | "insights" = "auto") {
    const trimmed = text.trim();
    if (!trimmed || uploading || sendingRef.current) return;
    sendingRef.current = true;
    setSending(true);
    setFailed(null);
    if (echo) {
      const userId = nextId();
      setMessages((prev) => [...prev, { id: userId, role: "user", text: trimmed }]);
    }
    try {
      const reply = await sendAssistantMessage(trimmed, patientId, {
        context, document_id: documentId,
        history: messages.slice(-6).map(message => ({ role: message.role, text: message.text.slice(0, 1000) })),
      });
      const replyId = nextId();
      setMessages((prev) => [...prev, toAssistantMessage(replyId, reply)]);
    } catch (err) {
      setFailed({ text: trimmed, message: toApiError(err).message, context });
    } finally {
      sendingRef.current = false;
      setSending(false);
    }
  }

  function updateCard(messageId: number, patch: Partial<ActionCard>) {
    setMessages((prev) =>
      prev.map((message) =>
        message.role === "assistant" && message.id === messageId && message.card
          ? { ...message, card: { ...message.card, ...patch } }
          : message,
      ),
    );
  }

  async function confirm(messageId: number, card: ActionCard) {
    if (card.status !== "pending" || inFlight.current.has(card.actionId)) return;
    inFlight.current.add(card.actionId);
    updateCard(messageId, { status: "confirming", error: null });
    try {
      await confirmAssistantAction(card.actionId);
      const done = `Done: ${card.summary}`;
      updateCard(messageId, { status: "confirmed" });
      const doneId = nextId();
      setMessages((prev) => [
        ...prev,
        { id: doneId, role: "assistant", text: done, citations: [], card: null },
      ]);
      showToast(done);
    } catch (err) {
      updateCard(messageId, { status: "failed", error: toApiError(err).message });
    } finally {
      inFlight.current.delete(card.actionId);
    }
  }

  async function dismiss(messageId: number, card: ActionCard) {
    if (!canDismiss(card.status) || inFlight.current.has(card.actionId)) return;
    inFlight.current.add(card.actionId);
    const previous = card.status;
    updateCard(messageId, { status: "dismissing", error: null });
    try {
      await dismissAssistantAction(card.actionId);
      updateCard(messageId, { status: "dismissed" });
    } catch (err) {
      updateCard(messageId, { status: previous, error: toApiError(err).message });
    } finally {
      inFlight.current.delete(card.actionId);
    }
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = input;
    setInput("");
    void send(text, true);
  }

  return (
    <div className="mx-auto flex min-h-[calc(100dvh-235px)] max-w-[820px] flex-col">
      {auth.state.status === "authed" && auth.state.user.role !== "patient" && <AssistantPatient value={patientId} onChange={changePatient} disabled={sending || uploading || messages.some(message => message.role === "assistant" && (message.card?.status === "confirming" || message.card?.status === "dismissing"))} />}
      <h1 className="mt-5 text-lg font-medium tracking-[-0.02em]">
        Terra assistant
      </h1>
      <p className="mt-1 max-w-xl text-xs leading-6 text-muted">
        {isPatient
          ? "Understand your prescriptions, review past records and manage appointments. Review and confirm any proposed booking change."
          : "Explore clinic Insights and coordinate patient appointments. Review and confirm any proposed booking change."}
      </p>

      <section
        aria-label="Conversation"
        className="mt-3 flex min-w-0 flex-1 flex-col"
      >
        <div
          ref={listRef}
          role="log"
          aria-live="polite"
          className="flex max-h-[48dvh] min-h-[180px] flex-1 flex-col gap-7 overflow-y-auto py-6 sm:min-h-[220px]"
        >
          {messages.length === 0 && !sending && (
            <div className="my-auto px-3 py-4 text-center">
              <h2 className="font-serif text-[clamp(1.9rem,4vw,2.7rem)] leading-tight tracking-[-0.03em]">{isPatient ? "How can I help with your care?" : "What can I help you with?"}</h2>
              <p className="mx-auto mt-4 max-w-sm text-sm leading-7 text-muted">{isPatient ? "Bring your prescriptions, questions and next steps into one conversation." : "Ask about your clinic, patient appointments or a selected record."}</p>
            </div>
          )}
          {messages.map((message) => (
            <MessageItem
              key={message.id}
              message={message}
              onOpenGuide={setOpenGuide}
              onConfirm={(card) => confirm(message.id, card)}
              onDismiss={(card) => dismiss(message.id, card)}
            />
          ))}
          {sending && (
            <div role="status" aria-live="polite" className="mr-auto flex items-center gap-2 text-sm text-muted">
              <span className="inline-block size-2 animate-pulse rounded-full bg-muted" aria-hidden="true" />
              Assistant is replying…
            </div>
          )}
          {failed && (
            <div role="alert" className="rounded-[3px] border border-danger p-4 text-sm">
              <p className="text-danger">
                The assistant could not reply. {failed.message}
              </p>
              <button
                type="button"
                onClick={() => void send(failed.text, false, failed.context)}
                disabled={sending}
                className={`${btnSecondary} mt-3`}
              >
                Retry
              </button>
            </div>
          )}
        </div>

        <div className="mt-auto pb-3 pt-4">
          <details className="mb-3" open={messages.length === 0}>
          <summary className="mb-3 w-fit cursor-pointer text-xs text-muted">Suggested questions</summary>
          <div className="flex flex-wrap gap-2" aria-label="Suggestions">
            {isPatient ? <>
              <button type="button" className={chipClass} disabled={sending} onClick={() => void send(documentId ? "Explain this document in plain English and flag unclear instructions." : "Explain my prescription in plain English and flag unclear instructions.", true, "documents")}>{documentId ? "Explain selected record" : "Explain prescription"}</button>
              <button type="button" className={chipClass} disabled={sending} onClick={() => void send("Summarize my dated past visit notes.", true, "documents")}>Past visit notes</button>
            </> : <>
              {patientId !== undefined && <button type="button" className={chipClass} disabled={sending} onClick={() => void send("Explain the current prescription.", true, "documents")}>Current prescription</button>}
              {isAdmin && patientId !== undefined && <button type="button" className={chipClass} disabled={sending} onClick={() => void send("Summarize the patient's dated past visit notes.", true, "documents")}>Patient medical history</button>}
              <button type="button" className={chipClass} disabled={sending} onClick={() => void send("Summarize clinic activity in the reporting window.", true, "insights")}>Clinic activity</button>
            </>}
            {SUGGESTIONS.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                disabled={sending}
                onClick={() => void send(suggestion, true)}
                className={chipClass}
              >
                {suggestion}
              </button>
            ))}
          </div>
          </details>
          <div className="rounded-3xl border border-line bg-panel p-3 sm:p-4">
          <form onSubmit={onSubmit}>
            <label htmlFor="assistant-message" className="sr-only">
              Your message
            </label>
            <textarea
              id="assistant-message"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={event => {
                if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
                  event.preventDefault();
                  if (!sending && !uploading && input.trim()) event.currentTarget.form?.requestSubmit();
                }
              }}
              autoComplete="off"
              placeholder={isPatient ? "Ask about your prescription, records or appointments" : "Ask about clinic performance or patient appointments"}
              maxLength={500}
              rows={2}
              className="min-h-[72px] w-full resize-y border-0 bg-transparent px-2 py-3 text-sm leading-6 text-ink placeholder:text-muted focus-visible:outline-offset-0"
            />
            <div className="flex items-end justify-between gap-3">
              <span className="px-2 text-xs text-muted">Enter to send · Shift + Enter for a new line</span>
            <button type="submit" aria-label="Send message" disabled={sending || uploading || input.trim() === ""} className="grid size-11 shrink-0 place-items-center rounded-full bg-ink text-panel transition hover:bg-accent disabled:cursor-not-allowed disabled:opacity-30">
              <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M12 19V5m-6 6 6-6 6 6" /></svg>
            </button>
            </div>
          </form>
          <div className="mt-2 border-t border-line pt-2">
            {(isPatient || patientId !== undefined) && <PatientRecords key={patientId ?? "self"} patientId={patientId} canUpload={isPatient} selected={documentId} onSelect={changeDocument} onUploadStateChange={setUploading} disabled={sending || messages.some(message => message.role === "assistant" && (message.card?.status === "confirming" || message.card?.status === "dismissing"))} />}
            {!isPatient && <Link href="/insights" className="inline-flex min-h-11 items-center px-3 text-xs text-muted hover:text-ink">Open clinic Insights →</Link>}
          </div>
          </div>
          <p className="mt-3 text-center text-xs leading-5 text-muted">AI-generated assistance. Check important information with your clinic. Booking changes need your confirmation.</p>
        </div>
      </section>

      <LiveRegion message={toast} />

      {openGuide && (
        <GuideDialog key={openGuide.slug} citation={openGuide} onClose={() => setOpenGuide(null)} />
      )}
    </div>
  );
}

function canDismiss(status: CardStatus): boolean {
  return status === "pending" || status === "failed";
}

function toAssistantMessage(id: number, reply: AssistantReply): ChatMessage {
  const action = reply.proposed_action;
  return {
    id,
    role: "assistant",
    text: reply.reply,
    citations: reply.citations,
    notice: reply.ai_notice,
    card: action
      ? {
          actionId: action.id,
          type: action.type,
          summary: action.summary,
          status: "pending",
          error: null,
        }
      : null,
  };
}

function MessageItem({
  message,
  onOpenGuide,
  onConfirm,
  onDismiss,
}: {
  message: ChatMessage;
  onOpenGuide: (citation: AssistantCitation) => void;
  onConfirm: (card: ActionCard) => void;
  onDismiss: (card: ActionCard) => void;
}) {
  if (message.role === "user") {
    return (
      <div className="ml-auto max-w-[85%] whitespace-pre-wrap break-words rounded-2xl bg-soft px-5 py-3 text-sm leading-7">
        <span className="sr-only">You: </span>
        {message.text}
      </div>
    );
  }

  return (
    <div className="mr-auto flex w-full min-w-0 flex-col gap-3">
      <div className="break-words px-2 py-1 text-sm leading-7">
        <span className="sr-only">Assistant: </span>
        <p className="whitespace-pre-line">{message.text}</p>
        {message.citations.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {message.citations.map((citation) => (
              citation.scope === "insights" ? <Link key={citation.slug} href="/insights" className="min-h-11 py-3 text-sm text-accent underline">View source in clinic Insights</Link> : <button
                key={citation.slug}
                type="button"
                onClick={() => onOpenGuide(citation)}
                className="inline-flex min-h-11 items-center rounded-[3px] border border-accent px-3 text-xs font-medium text-accent hover:bg-soft"
              >
                {citation.slug.startsWith("doc-") ? "Source" : "Guide"}: {citation.title}
              </button>
            ))}
          </div>
        )}
      </div>
      {message.notice && <p className="flex items-start gap-2 text-xs leading-6 text-muted">
        <span aria-hidden="true" className="mt-1 grid h-4 w-4 shrink-0 place-items-center rounded-full border border-accent font-bold text-accent">!</span>
        <span>{message.notice}</span>
      </p>}
      {message.card && (
        <ActionCardView card={message.card} onConfirm={onConfirm} onDismiss={onDismiss} />
      )}
    </div>
  );
}

function ActionCardView({
  card,
  onConfirm,
  onDismiss,
}: {
  card: ActionCard;
  onConfirm: (card: ActionCard) => void;
  onDismiss: (card: ActionCard) => void;
}) {
  const busy = card.status === "confirming" || card.status === "dismissing";
  const showConfirm = card.status === "pending" || card.status === "confirming";
  const showDismiss = canDismiss(card.status) || card.status === "dismissing";

  let statusText: string | null = null;
  if (card.status === "confirmed") statusText = "Confirmed.";
  if (card.status === "dismissed") statusText = "Dismissed. Nothing was changed.";

  return (
    <section
      aria-label="Proposed action"
      className="rounded-[4px] border-2 border-accent bg-soft p-4 text-sm"
    >
      <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-accent">
        {ACTION_LABEL[card.type]}
      </p>
      <p className="mt-2 leading-6">{card.summary}</p>
      {card.error && (
        <p role="alert" className="mt-3 text-danger">
          {card.error}
        </p>
      )}
      {statusText && <p className="mt-3 text-muted">{statusText}</p>}
      {(showConfirm || showDismiss) && (
        <div className="mt-4 flex flex-wrap gap-3">
          {showConfirm && (
            <button
              type="button"
              disabled={busy}
              aria-busy={card.status === "confirming"}
              onClick={() => onConfirm(card)}
              className={btnPrimary}
            >
              {card.status === "confirming" ? "Confirming…" : "Confirm"}
            </button>
          )}
          {showDismiss && (
            <button
              type="button"
              disabled={busy}
              onClick={() => onDismiss(card)}
              className={btnSecondary}
            >
              {card.status === "dismissing" ? "Dismissing…" : "Dismiss"}
            </button>
          )}
        </div>
      )}
    </section>
  );
}

function GuideDialog({
  citation,
  onClose,
}: {
  citation: AssistantCitation;
  onClose: () => void;
}) {
  const load = useCallback(() => citation.scope === "patient" ? getPatientDocument(citation.slug, citation.patient_id ?? undefined) : getGuide(citation.slug), [citation.slug, citation.scope, citation.patient_id]);
  const { state, retry } = useLoader(load);

  return (
    <Modal title={citation.title} onClose={onClose}>
      {state.status === "loading" && <Skeleton lines={5} />}
      {state.status === "error" && (
        <ErrorState title="Could not load this guide" message={state.error.message} onRetry={retry} />
      )}
      {state.status === "ready" && (
        <p className="whitespace-pre-line text-sm leading-7">{state.data.body}</p>
      )}
    </Modal>
  );
}
