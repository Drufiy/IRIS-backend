// Screen outline state machine — driven by WebSocket from Python IPCBridge

const ws = new WebSocket("ws://localhost:7788");

const STATE_CONFIG = {
  IDLE:        { color: "#FFFFFF", animation: "static",     opacity: 1 },
  INTERACTIVE: { color: "#3B82F6", animation: "pulse-slow", opacity: 1 },
  ACTING:      { color: "#22C55E", animation: "sweep",      opacity: 1 },
  DONE:        { color: "#3B82F6", animation: "static",     opacity: 1 },
  STOPPING:    { color: "#FFFFFF", animation: "static",     opacity: 0 },
};

const outline = document.getElementById("outline");

ws.onopen = () => {
  console.log("IPC connected");
  applyState("IDLE");
};

ws.onclose = () => {
  console.log("IPC disconnected — retrying in 2s");
  setTimeout(() => location.reload(), 2000);
};

ws.onmessage = (msg) => {
  const data = JSON.parse(msg.data);
  if (data.event === "state_change") {
    applyState(data.state);
  }
  if (data.event === "approval_request") {
    showApprovalPopup(data);
  }
};

function applyState(state) {
  const cfg = STATE_CONFIG[state] || STATE_CONFIG.IDLE;
  outline.style.borderColor = cfg.color;
  outline.style.boxShadow = `inset 0 0 0 3px ${cfg.color}, 0 0 12px ${cfg.color}40`;
  outline.className = `outline-${cfg.animation}`;

  if (state === "STOPPING") {
    setTimeout(() => { outline.style.opacity = "0"; }, 600);
    setTimeout(() => { outline.style.display = "none"; }, 1000);
  } else {
    outline.style.display = "block";
    outline.style.opacity = "1";
  }
}

function showApprovalPopup(data) {
  // Remove any existing popup
  const existing = document.getElementById("approval-popup");
  if (existing) existing.remove();

  const popup = document.createElement("div");
  popup.id = "approval-popup";
  popup.innerHTML = `
    <div class="approval-content">
      <p><strong>${data.action}</strong></p>
      <p class="approval-params">${JSON.stringify(data.params, null, 2)}</p>
      <div class="approval-buttons">
        <button id="approve-btn" class="btn-approve">Approve</button>
        <button id="deny-btn" class="btn-deny">Deny</button>
      </div>
    </div>
  `;
  document.body.appendChild(popup);

  document.getElementById("approve-btn").onclick = () => {
    ws.send(JSON.stringify({ event: "approval_response", id: data.id, approved: true }));
    popup.remove();
  };
  document.getElementById("deny-btn").onclick = () => {
    ws.send(JSON.stringify({ event: "approval_response", id: data.id, approved: false }));
    popup.remove();
  };
}
