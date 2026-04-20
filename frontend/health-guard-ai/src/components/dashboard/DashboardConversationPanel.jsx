import { useEffect, useRef, useState } from "react";
import notificationSound from "../../audio/notification-sound.mp3";

const AUTO_NO_RESPONSE_SECONDS = 10;
const AUTO_NO_RESPONSE_TRIGGER = "no_response_";

function ChatBubble({ message }) {
  const { role, text } = message;
  const isAssistant = role === "assistant";

  return (
    <div style={{ display: "flex", justifyContent: isAssistant ? "flex-start" : "flex-end" }}>
      <div className={`dashboard-chat-bubble ${isAssistant ? "bubble-assistant" : "bubble-user"}`}>
        <div className="dashboard-chat-role">
          {isAssistant ? "Communication Agent" : "User"}
        </div>
        <div style={{ fontSize: 11, color: "var(--text)", lineHeight: 1.6 }}>{text}</div>
      </div>
    </div>
  );
}

function TypingBubble() {
  return (
    <div style={{ display: "flex", justifyContent: "flex-start" }}>
      <div className="dashboard-chat-bubble bubble-assistant dashboard-typing-bubble">
        <div className="dashboard-chat-role">Communication Agent</div>
        <div style={{ fontSize: 10, color: "var(--text-muted)", fontStyle: "italic", marginTop: 4 }}>
          Thinking....
        </div>
      </div>
    </div>
  );
}

export default function DashboardConversationPanel({
  profile,
  latestTurn,
  messages,
  draftMessage,
  setDraftMessage,
  phase,
  sendTurn,
}) {
  const hasAssistantMessage = messages.some((message) => message.role === "assistant" && message.text?.trim());
  const isAgentTyping = phase === "sending" || (phase === "starting" && !hasAssistantMessage);
  const isReasoningActive = latestTurn?.reasoning_status === "pending" || latestTurn?.state === "reasoning_in_progress";
  const isAwaitingReply = latestTurn?.communication_analysis?.guidance_intent !== "instruction";
  const isDispatchConfirmationPending =
    latestTurn?.state === "awaiting_dispatch_confirmation" ||
    latestTurn?.execution_state?.dispatch_status === "pending_confirmation" ||
    (latestTurn?.action_states || []).some(
      (state) => state.action_type === "emergency_dispatch" && state.status === "pending_confirmation",
    );
  const isDispatchCompleted =
    latestTurn?.execution_state?.dispatch_status === "confirmed" ||
    latestTurn?.execution_state?.dispatch_status === "auto_dispatched" ||
    latestTurn?.execution_state?.dispatch_status === "dispatched" ||
    (latestTurn?.action_states || []).some(
      (state) => state.action_type === "emergency_dispatch" && state.status === "completed",
    ) ||
    (latestTurn?.execution_updates || []).some(
      (update) => update.type === "emergency_dispatch" && update.status === "completed",
    );
  const [showPostReasoningReply, setShowPostReasoningReply] = useState(false);
  const [autoNoResponseCountdown, setAutoNoResponseCountdown] = useState(0);
  const previousReasoningStatusRef = useRef(latestTurn?.reasoning_status || "");
  const streamEndRef = useRef(null);
  const noResponseTimerRef = useRef(null);
  const sendTurnRef = useRef(sendTurn);
  const audioRef = useRef(null);
  const assistantCountRef = useRef(messages.filter((m) => m.role === "assistant").length);

  const lastMessage = messages[messages.length - 1] || null;
  const lastAssistantMessageIndex = [...messages]
    .map((message, index) => ({ message, index }))
    .reverse()
    .find((entry) => entry.message.role === "assistant" && entry.message.text?.trim())?.index ?? -1;
  const lastAssistantMessage = lastAssistantMessageIndex >= 0 ? messages[lastAssistantMessageIndex] : null;
  const shouldShowNoResponseCountdown =
    Boolean(lastAssistantMessage) &&
    lastMessage?.role === "assistant" &&
    isAwaitingReply &&
    !isAgentTyping &&
    !isReasoningActive &&
    !isDispatchConfirmationPending &&
    !isDispatchCompleted &&
    phase !== "sending" &&
    phase !== "idle" &&
    phase !== "completed" &&
    !draftMessage.trim();

  const recommendedReplies = (phase === "sending" || phase === "idle")
    ? []
    : [
        ...(showPostReasoningReply ? ["What should I do now?"] : []),
        ...(latestTurn?.quick_replies || []),
      ].filter((reply, index, replies) => replies.indexOf(reply) === index);

  useEffect(() => {
    streamEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isAgentTyping]);

  useEffect(() => {
    sendTurnRef.current = sendTurn;
  }, [sendTurn]);

  useEffect(() => {
    if (!audioRef.current) {
      audioRef.current = new Audio(notificationSound);
    }
  }, []);

  useEffect(() => {
    const currentAssistantCount = messages.filter((m) => m.role === "assistant" && m.text?.trim()).length;
    if (currentAssistantCount > assistantCountRef.current) {
      audioRef.current?.play().catch((err) => {
        console.warn("Audio playback failed:", err);
      });
    }
    assistantCountRef.current = currentAssistantCount;
  }, [messages]);

  useEffect(() => {
    const previousStatus = previousReasoningStatusRef.current;
    const currentStatus = latestTurn?.reasoning_status || "";

    if (previousStatus === "pending" && currentStatus === "completed") {
      setShowPostReasoningReply(true);
      if (!draftMessage.trim()) {
        setDraftMessage("What should I do now?");
      }
    }

    if (currentStatus === "pending") {
      setShowPostReasoningReply(false);
    }

    previousReasoningStatusRef.current = currentStatus;
  }, [draftMessage, latestTurn?.reasoning_status, setDraftMessage]);

  useEffect(() => {
    if (!shouldShowNoResponseCountdown) {
      setAutoNoResponseCountdown(0);
      if (noResponseTimerRef.current) {
        window.clearInterval(noResponseTimerRef.current);
        noResponseTimerRef.current = null;
      }
      return undefined;
    }

    setAutoNoResponseCountdown(AUTO_NO_RESPONSE_SECONDS);
    if (noResponseTimerRef.current) {
      window.clearInterval(noResponseTimerRef.current);
    }

    let secondsLeft = AUTO_NO_RESPONSE_SECONDS;

    noResponseTimerRef.current = window.setInterval(() => {
      secondsLeft -= 1;
      setAutoNoResponseCountdown(secondsLeft);

      if (secondsLeft <= 0) {
        if (noResponseTimerRef.current) {
          window.clearInterval(noResponseTimerRef.current);
          noResponseTimerRef.current = null;
        }
        sendTurnRef.current(AUTO_NO_RESPONSE_TRIGGER);
      }
    }, 1000);

    return () => {
      if (noResponseTimerRef.current) {
        window.clearInterval(noResponseTimerRef.current);
        noResponseTimerRef.current = null;
      }
    };
  }, [lastAssistantMessageIndex, shouldShowNoResponseCountdown]);

  return (
    <div style={{ display: "flex", flexDirection: "column", flex: 1, overflow: "hidden" }}>
      <div className="card-title" style={{ margin: "20px 20px 10px" }}>Conversation Loop</div>

      {messages.length === 0 && (
        <div className="empty-state" style={{ minHeight: 140, marginBottom: 14 }}>
          <span className="empty-icon">AI</span>
          <p>
            No active session for {profile.name}.<br />
            Start the agent flow from the setup card to begin.
          </p>
        </div>
      )}

      <div className="dashboard-chat-stream">
        {messages.map((message, index) => (
          <ChatBubble key={`${message.role}-${index}`} message={message} />
        ))}
        {shouldShowNoResponseCountdown && autoNoResponseCountdown > 0 && (
          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <div
              className="dashboard-chat-bubble bubble-user"
              style={{
                borderColor: "rgba(220, 38, 38, 0.35)",
                boxShadow: "0 0 0 1px rgba(220, 38, 38, 0.08)",
              }}
            >
              <div className="dashboard-chat-role">User</div>
              <div style={{ fontSize: 11, color: "var(--text)", lineHeight: 1.6 }}>
                No response in {autoNoResponseCountdown}s...
              </div>
            </div>
          </div>
        )}
        {isAgentTyping && <TypingBubble />}
        <div ref={streamEndRef} />
      </div>

      <div style={{ borderTop: "1px solid var(--border)", padding: "14px 20px 24px" }}>
        {recommendedReplies.length > 0 && (
          <div style={{ marginBottom: 14 }}>
            <div
              style={{
                fontSize: 9,
                fontWeight: 700,
                letterSpacing: "0.06em",
                textTransform: "uppercase",
                color: "var(--text-muted)",
                marginBottom: 8,
              }}
            >
              Recommended Responses
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {recommendedReplies.map((reply) => (
                <button
                  key={reply}
                  className="btn btn-ghost btn-sm"
                  onClick={() => {
                    if (reply === "What should I do now?") {
                      setShowPostReasoningReply(false);
                    }
                    sendTurn(reply);
                  }}
                  disabled={isReasoningActive}
                >
                  {reply}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="form-group">
          <textarea
            className="form-input"
            style={{ resize: "none" }}
            rows="3"
            value={draftMessage}
            onChange={(event) => setDraftMessage(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                if (draftMessage.trim() && phase !== "sending" && latestTurn && !isReasoningActive) {
                  if (draftMessage.trim() === "What should I do now?") {
                    setShowPostReasoningReply(false);
                  }
                  sendTurn();
                }
              }
            }}
            placeholder={
              phase === "idle"
                ? "Start a session to interact"
                : isReasoningActive
                ? "The agent is reasoning. Please wait..."
                : "Type your response"
            }
            disabled={isReasoningActive || phase === "idle"}
          />
        </div>

        <button
          className="btn btn-green"
          style={{ width: "100%", justifyContent: "center" }}
          onClick={() => {
            if (draftMessage.trim() && !isReasoningActive) {
              if (draftMessage.trim() === "What should I do now?") {
                setShowPostReasoningReply(false);
              }
              sendTurn();
            }
          }}
          disabled={!draftMessage.trim() || phase === "sending" || !latestTurn || isReasoningActive || phase === "idle"}
        >
          {isReasoningActive ? "Reasoning..." : phase === "sending" ? "Waiting for agent..." : phase === "idle" ? "Session Stopped" : "Send"}
        </button>
      </div>
    </div>
  );
}
