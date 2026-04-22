// Replace with your Render.com backend URL after deployment
const API = "https://tony-stark-assistant.onrender.com";

// ── State ──────────────────────────────────────────────────────────────────
let awaitingDestination = false;
let isSpeaking = false;
let recognition = null;

// ── DOM ────────────────────────────────────────────────────────────────────
const conversation  = document.getElementById("conversation");
const statusDot     = document.getElementById("statusDot");
const statusText    = document.getElementById("statusText");
const micBtn        = document.getElementById("micBtn");
const micHint       = document.getElementById("micHint");
const destRow       = document.getElementById("destRow");
const destInput     = document.getElementById("destInput");
const destSubmit    = document.getElementById("destSubmit");

// ── Speech Synthesis (TTS) ─────────────────────────────────────────────────
function speak(text, onDone) {
  window.speechSynthesis.cancel();
  const utt = new SpeechSynthesisUtterance(text);
  utt.lang = "en-GB";
  utt.rate = 1.0;
  utt.pitch = 0.9;

  // Pick a good voice if available
  const voices = window.speechSynthesis.getVoices();
  const preferred = voices.find(v =>
    v.lang.startsWith("en") && (v.name.includes("Google") || v.name.includes("Daniel") || v.name.includes("Samantha"))
  );
  if (preferred) utt.voice = preferred;

  setStatus("speaking", "Speaking…");
  isSpeaking = true;

  utt.onend = () => {
    isSpeaking = false;
    setStatus("ready", "Ready");
    if (onDone) onDone();
  };
  utt.onerror = () => {
    isSpeaking = false;
    setStatus("ready", "Ready");
    if (onDone) onDone();
  };

  window.speechSynthesis.speak(utt);
}

// ── Speech Recognition (STT) ───────────────────────────────────────────────
function startListening(onResult) {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    addMessage("system", "Speech recognition not supported in this browser. Please use Chrome.");
    return;
  }

  recognition = new SR();
  recognition.lang = "en-US";
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;

  setStatus("listening", "Listening…");
  micBtn.classList.add("listening");
  micHint.textContent = "Listening… speak now";

  recognition.onresult = e => {
    const text = e.results[0][0].transcript;
    micBtn.classList.remove("listening");
    addMessage("user", text);
    onResult(text);
  };

  recognition.onerror = e => {
    micBtn.classList.remove("listening");
    setStatus("ready", "Ready");
    micHint.textContent = "Tap the mic and speak";
    if (e.error !== "no-speech") {
      addMessage("system", "Couldn't hear that — please try again.");
    }
  };

  recognition.onend = () => {
    micBtn.classList.remove("listening");
    if (!isSpeaking) setStatus("ready", "Ready");
  };

  recognition.start();
}

// ── UI Helpers ─────────────────────────────────────────────────────────────
function setStatus(state, text) {
  statusDot.className = "status-dot " + state;
  statusText.textContent = text;
}

function addMessage(role, text) {
  if (role === "thinking") {
    const el = document.createElement("div");
    el.className = "thinking-dots";
    el.id = "thinking";
    el.innerHTML = "<span></span><span></span><span></span>";
    conversation.appendChild(el);
    conversation.scrollTop = conversation.scrollHeight;
    return;
  }

  document.getElementById("thinking")?.remove();

  const el = document.createElement("div");
  el.className = "message " + role;

  if (role === "assistant") {
    el.innerHTML = `<div class="label">J.A.R.V.I.S.</div>${escHtml(text)}`;
  } else if (role === "user") {
    el.textContent = text;
  } else {
    el.textContent = text;
  }

  conversation.appendChild(el);
  conversation.scrollTop = conversation.scrollHeight;
}

function escHtml(t) {
  return t.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

// ── API Calls ──────────────────────────────────────────────────────────────
async function fetchJSON(path) {
  const res = await fetch(API + path);
  return res.json();
}

// ── Core Flows ─────────────────────────────────────────────────────────────
async function runMorningBriefing() {
  setStatus("thinking", "Gathering briefing…");
  addMessage("thinking");

  try {
    const data = await fetchJSON("/briefing/phase1");
    addMessage("assistant", data.text);
    speak(data.text, () => {
      // After speaking phase 1, ask for destination
      addMessage("assistant", "Where are you heading today?");
      speak("Where are you heading today?", () => {
        awaitingDestination = true;
        showDestinationInput();
      });
    });
  } catch (e) {
    addMessage("system", "Could not reach the server. Check your connection.");
    setStatus("ready", "Ready");
  }
}

async function fetchTransit(destination) {
  setStatus("thinking", "Looking up route…");
  addMessage("thinking");
  hideDestinationInput();
  awaitingDestination = false;

  try {
    const data = await fetchJSON(`/briefing/transit?destination=${encodeURIComponent(destination)}`);
    addMessage("assistant", data.text);
    speak(data.text, () => {
      addMessage("assistant", "Have a great day.");
      speak("Have a great day.");
    });
  } catch (e) {
    addMessage("system", "Could not fetch transit info.");
    setStatus("ready", "Ready");
  }
}

async function handleCommand(text) {
  const t = text.toLowerCase().trim();

  if (awaitingDestination) {
    fetchTransit(text);
    return;
  }

  if (t.includes("good morning") || t.includes("brief me") || t.includes("morning")) {
    runMorningBriefing();
    return;
  }

  if (t.includes("weather") || t.includes("rain") || t.includes("umbrella")) {
    const loc = extractLocation(t) || "Munich";
    setStatus("thinking", "Fetching weather…");
    addMessage("thinking");
    const endpoint = t.includes("rain") ? `/rain?location=${encodeURIComponent(loc)}` : `/weather?location=${encodeURIComponent(loc)}`;
    const data = await fetchJSON(endpoint);
    addMessage("assistant", data.text);
    speak(data.text);
    return;
  }

  if (t.includes("strike") || t.includes("disruption") || t.includes("delay")) {
    setStatus("thinking", "Checking disruptions…");
    addMessage("thinking");
    const data = await fetchJSON("/transit/disruptions");
    addMessage("assistant", data.text);
    speak(data.text);
    return;
  }

  if (t.includes("going to") || t.includes("route to") || t.includes("get to") || t.includes("how do i get")) {
    const dest = extractDestination(t);
    if (dest) {
      setStatus("thinking", "Finding route…");
      addMessage("thinking");
      const data = await fetchJSON(`/transit/route?destination=${encodeURIComponent(dest)}`);
      addMessage("assistant", data.text);
      speak(data.text);
    } else {
      addMessage("assistant", "Where would you like to go?");
      speak("Where would you like to go?", () => {
        awaitingDestination = true;
        showDestinationInput();
      });
    }
    return;
  }

  if (t.includes("next") && (t.includes("u") || t.includes("tram") || t.includes("bus"))) {
    setStatus("thinking", "Fetching departures…");
    addMessage("thinking");
    const data = await fetchJSON(`/transit/departures?station=${encodeURIComponent("Klinikum Großhadern")}`);
    addMessage("assistant", data.text);
    speak(data.text);
    return;
  }

  if (t.includes("forex") || t.includes("market") || t.includes("news") || t.includes("dollar")) {
    setStatus("thinking", "Fetching market news…");
    addMessage("thinking");
    const data = await fetchJSON("/forex");
    addMessage("assistant", data.text);
    speak(data.text);
    return;
  }

  addMessage("assistant", "I can help with your morning briefing, weather, transit routes, or market news. What do you need?");
  speak("I can help with your morning briefing, weather, transit routes, or market news. What do you need?");
}

function extractDestination(text) {
  const m = text.match(/(?:going to|route to|get to|take me to|how do i get to)\s+(.+?)(?:\?|$)/i);
  return m ? m[1].trim() : null;
}

function extractLocation(text) {
  const m = text.match(/(?:in|at|for)\s+([a-z\s]+?)(?:\s+today|\s+now|\?|$)/i);
  return m ? m[1].trim() : null;
}

// ── Destination Input ──────────────────────────────────────────────────────
function showDestinationInput() {
  destRow.classList.remove("hidden");
  destInput.focus();
  micHint.textContent = "Type or tap mic to say your destination";
}

function hideDestinationInput() {
  destRow.classList.add("hidden");
  destInput.value = "";
  micHint.textContent = "Tap the mic and speak";
}

// ── Event Listeners ────────────────────────────────────────────────────────
micBtn.addEventListener("click", () => {
  if (isSpeaking) {
    window.speechSynthesis.cancel();
    isSpeaking = false;
  }
  startListening(handleCommand);
});

destSubmit.addEventListener("click", () => {
  const val = destInput.value.trim();
  if (val) {
    addMessage("user", val);
    fetchTransit(val);
  }
});

destInput.addEventListener("keydown", e => {
  if (e.key === "Enter") destSubmit.click();
});

// Quick buttons
document.getElementById("btnMorning").addEventListener("click", () => {
  addMessage("user", "Good morning");
  runMorningBriefing();
});

document.getElementById("btnWeather").addEventListener("click", async () => {
  addMessage("user", "What's the weather?");
  setStatus("thinking", "Fetching weather…");
  addMessage("thinking");
  const data = await fetchJSON("/weather?location=Munich");
  addMessage("assistant", data.text);
  speak(data.text);
});

document.getElementById("btnTransit").addEventListener("click", () => {
  addMessage("assistant", "Where would you like to go?");
  speak("Where would you like to go?", () => {
    awaitingDestination = true;
    showDestinationInput();
  });
});

document.getElementById("btnDisruptions").addEventListener("click", async () => {
  addMessage("user", "Any disruptions?");
  setStatus("thinking", "Checking disruptions…");
  addMessage("thinking");
  const data = await fetchJSON("/transit/disruptions");
  addMessage("assistant", data.text);
  speak(data.text);
});

// ── Init ───────────────────────────────────────────────────────────────────
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js");
}

window.speechSynthesis.onvoiceschanged = () => {};

// Greet on load
setTimeout(() => {
  addMessage("assistant", "Good morning. Tap 'Morning Briefing' or the mic to get started.");
}, 300);
