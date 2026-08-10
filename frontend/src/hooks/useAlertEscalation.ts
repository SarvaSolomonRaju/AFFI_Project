import { useEffect, useRef, useState } from "react";
import type { AlertLevel } from "../types/api";

const LEVEL_RANK: Record<AlertLevel, number> = { GREEN: 0, ADVISORY: 1, WATCH: 2, WARNING: 3 };
const STORAGE_KEY = "affi_alerts_enabled";

// Synthesized tone via Web Audio — no external asset, works offline, and
// browsers require a user gesture before any audio plays, which enable()
// below provides.
function beep(freq: number, durationMs: number, delayMs = 0) {
  setTimeout(() => {
    try {
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const ctx = new AudioCtx();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "square";
      osc.frequency.value = freq;
      gain.gain.value = 0.15;
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + durationMs / 1000);
      osc.onended = () => ctx.close();
    } catch {
      // Web Audio unavailable/blocked — silent no-op, never breaks the dashboard.
    }
  }, delayMs);
}

// Two rising tones for WARNING (the level demanding immediate action), a
// single tone for any other escalation — audibly distinct from each other.
function playEscalationTone(level: AlertLevel) {
  if (level === "WARNING") {
    beep(880, 220, 0);
    beep(1046, 260, 260);
  } else {
    beep(660, 200, 0);
  }
}

// Fires an audible tone + browser push notification the moment a live alert
// level ESCALATES — never on de-escalation, never on first load (nobody
// needs an alarm for "still GREEN"). A 60s poll only helps if someone is
// staring at the tab; this is for the manager who's stepped away mid-shift.
// Opt-in and persisted in localStorage since both sound and Notification
// permission require a user gesture to unlock in every modern browser.
export function useAlertEscalation(level: AlertLevel | null | undefined) {
  const [enabled, setEnabled] = useState<boolean>(() => localStorage.getItem(STORAGE_KEY) === "1");
  const prevLevel = useRef<AlertLevel | null>(null);
  const firstRun = useRef(true);

  useEffect(() => {
    if (!level) return;
    if (firstRun.current) {
      firstRun.current = false;
      prevLevel.current = level;
      return;
    }
    const prev = prevLevel.current;
    prevLevel.current = level;
    if (!enabled || !prev || LEVEL_RANK[level] <= LEVEL_RANK[prev]) return;

    playEscalationTone(level);
    if (typeof Notification !== "undefined" && Notification.permission === "granted") {
      new Notification(`FloodAI: ${level}`, {
        body: `Alert escalated from ${prev} to ${level} — Upper Sonoita Creek`,
        tag: "affi-alert-escalation",
      });
    }
  }, [level, enabled]);

  function enable() {
    localStorage.setItem(STORAGE_KEY, "1");
    setEnabled(true);
    if (typeof Notification !== "undefined" && Notification.permission === "default") {
      Notification.requestPermission();
    }
    // Unlock the audio context with this click so a later automatic tone
    // (triggered by a poll tick, not a click) isn't silently blocked.
    beep(440, 1);
  }

  function disable() {
    localStorage.setItem(STORAGE_KEY, "0");
    setEnabled(false);
  }

  return { enabled, enable, disable };
}
