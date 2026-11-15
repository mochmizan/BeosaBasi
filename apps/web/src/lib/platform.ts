const ua = typeof navigator === "undefined" ? "" : navigator.userAgent || "";

export const isMac = /Mac|iPhone|iPad|iPod/i.test(ua);

// Includes a trailing space on Windows so `{modKey}K` reads "Ctrl K".
export const modKey = isMac ? "⌘" : "Ctrl ";
