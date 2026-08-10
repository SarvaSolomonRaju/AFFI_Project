// Shape/icon per alert level so the fastest-read signal on the dashboard
// doesn't depend on hue alone — plain red/orange/yellow/green is
// indistinguishable to the ~8% of men with red-green color blindness.
// Every badge that colors itself by alert level should prefix this icon.
export const ALERT_ICON: Record<string, string> = {
  GREEN: "●",     // ● filled circle
  ADVISORY: "▲",  // ▲ triangle
  WATCH: "◆",     // ◆ diamond
  WARNING: "✖",   // ✕ heavy cross
};

export function alertIcon(level: string | undefined | null): string {
  return ALERT_ICON[level ?? ""] ?? "●";
}
