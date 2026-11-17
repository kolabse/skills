"use strict";

const token = location.hash.slice(1);
const status = document.getElementById("status");
const messages = document.getElementById("messages");
const seen = new Set();

async function refresh() {
  try {
    const response = await fetch("/messages", {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (!response.ok) throw new Error(String(response.status));
    for (const { origin, actor, message } of await response.json()) {
      const key = JSON.stringify([origin, actor, message.id]);
      if (seen.has(key)) continue;
      const entry = document.createElement("li");
      const heading = document.createElement("strong");
      const body = document.createElement("p");
      const room = new URL(origin).pathname.split("/").filter(Boolean).pop();
      heading.textContent = `${room} · ${message.actor}${message.reply_to ? ` · reply to #${message.reply_to}` : ""}`;
      body.textContent = message.body;
      entry.append(heading, body);
      messages.append(entry);
      seen.add(key);
    }
    status.textContent = seen.size ? "Connected" : "No messages yet";
  } catch {
    status.textContent = "Transcript unavailable. Retrying…";
  }
  setTimeout(refresh, 2000);
}

if (token) refresh();
else status.textContent = "Open the private panel link to connect.";
