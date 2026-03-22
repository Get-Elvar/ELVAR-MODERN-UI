const API_TOKEN = "__ELVAR_API_TOKEN__";
const JSON_HEADERS = {"Content-Type": "application/json", "X-Elvar-Token": API_TOKEN};
const AUTH_HEADERS = {"X-Elvar-Token": API_TOKEN};

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "add-to-elvar",
    title: "Add to Elvar Workflow...",
    contexts: ["link", "page"]
  });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== "add-to-elvar") return;
  const url = info.linkUrl || info.pageUrl;
  if (!url) return;
  try {
    await fetch("http://127.0.0.1:31337/", {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify({ action: "add_to_workflow_dialog", url, title: tab?.title || "" })
    });
  } catch (e) {
    console.error("Elvar not reachable", e);
  }
});
