const API_TOKEN = "__ELVAR_API_TOKEN__";
const JSON_HEADERS = {"Content-Type": "application/json", "X-Elvar-Token": API_TOKEN};
const AUTH_HEADERS = {"X-Elvar-Token": API_TOKEN};

const msg = document.getElementById("msg");
const wfList = document.getElementById("wfList");

function show(text, isErr = false) {
  msg.style.color = isErr ? "#f88" : "#9ad";
  msg.textContent = text;
}

async function loadWorkflows() {
  wfList.innerHTML = "";
  try {
    const r = await fetch("http://127.0.0.1:31337/workflows", { headers: AUTH_HEADERS });
    if (!r.ok) throw new Error("HTTP " + r.status);
    const data = await r.json();
    const list = data.workflows || [];
    if (!list.length) {
      wfList.innerHTML = "<div>No workflows found.</div>";
      return;
    }

    for (const wf of list) {
      const b = document.createElement("button");
      b.textContent = wf.is_protected ? `${wf.name} (Protected)` : wf.name;
      b.onclick = async () => {
        try {
          const body = { action: "launch_workflow", name: wf.name, incognito: false, new_window: false };
          if (wf.is_protected) {
            const pwd = prompt(`Password for ${wf.name}:`);
            if (!pwd) return;
            body.password = pwd;
          }
          const rr = await fetch("http://127.0.0.1:31337/", { method: "POST", headers: JSON_HEADERS, body: JSON.stringify(body) });
          if (!rr.ok) throw new Error("launch failed");
          show(`Launched ${wf.name}`);
          setTimeout(() => window.close(), 900);
        } catch (e) {
          show("Failed to launch workflow.", true);
        }
      };
      wfList.appendChild(b);
    }
  } catch (e) {
    show("Could not connect to Elvar.", true);
  }
}

async function saveCurrentTabs() {
  try {
    const tabs = await chrome.tabs.query({ currentWindow: true });
    const urls = tabs.map(t => t.url).filter(u => typeof u === "string" && u.startsWith("http"));
    if (!urls.length) {
      show("No valid tabs to save.", true);
      return;
    }
    const payload = {
      action: "save_session",
      target: "_new_session",
      name: "Browser Session " + new Date().toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"}),
      urls,
      save_type: "session"
    };
    const r = await fetch("http://127.0.0.1:31337/", { method: "POST", headers: JSON_HEADERS, body: JSON.stringify(payload) });
    if (!r.ok) throw new Error("save failed");
    show("Saved session.");
  } catch (e) {
    show("Save failed.", true);
  }
}

document.getElementById("saveBtn").addEventListener("click", saveCurrentTabs);
document.getElementById("refreshBtn").addEventListener("click", loadWorkflows);
loadWorkflows();
