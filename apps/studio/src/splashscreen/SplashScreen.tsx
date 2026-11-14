import { useEffect, useState } from "react";
import { useReducedMotion } from "../lib/useReducedMotion";

const ODI_MASCOT = `/odi-mascot.svg`;

export default function SplashScreen() {
  const prefersReducedMotion = useReducedMotion();
  const [theme, setTheme] = useState<"light" | "dark">("dark");

  useEffect(() => {
    const root = document.documentElement;
    const stored = localStorage.getItem("studio.settings");
    let currentTheme: "light" | "dark" = "dark";
    if (stored) {
      try {
        const parsed = JSON.parse(stored);
        if (parsed.theme === "light" || parsed.theme === "dark") {
          currentTheme = parsed.theme;
        }
      } catch {
        /* ignore */
      }
    } else if (
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-color-scheme: light)").matches
    ) {
      currentTheme = "light";
    }
    setTheme(currentTheme);
    root.classList.add(currentTheme === "light" ? "theme-light" : "theme-dark");
    root.style.colorScheme = currentTheme;

    const mediaQuery = window.matchMedia("(prefers-color-scheme: light)");
    const handler = (e: MediaQueryListEvent) => {
      if (!localStorage.getItem("studio.settings")) {
        const newTheme = e.matches ? "light" : "dark";
        setTheme(newTheme);
        root.classList.remove(newTheme === "light" ? "theme-dark" : "theme-light");
        root.classList.add(newTheme === "light" ? "theme-light" : "theme-dark");
        root.style.colorScheme = newTheme;
      }
    };
    mediaQuery.addEventListener("change", handler);
    return () => mediaQuery.removeEventListener("change", handler);
  }, []);

  return (
    <div
      className="splash-screen"
      role="img"
      aria-label="Living Studio loading"
      data-theme={theme}
    >
      <div className="splash-screen__content">
        <img
          src={ODI_MASCOT}
          alt=""
          aria-hidden="true"
          className="splash-screen__mascot"
          style={{
            animation: prefersReducedMotion ? "none" : "float 3s ease-in-out infinite",
          }}
        />
        <span className="splash-screen__wordmark">Living Studio</span>
      </div>
      <style jsx>{`
        .splash-screen {
          height: 100%;
          display: flex;
          align-items: center;
          justify-content: center;
          background: var(--boot-bg);
        }
        .splash-screen[data-theme="light"] {
          --boot-bg: #f5f6f8;
        }
        .splash-screen[data-theme="dark"] {
          --boot-bg: #0a0b0e;
        }
        .splash-screen__content {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 16px;
        }
        .splash-screen__mascot {
          width: 96px;
          height: 96px;
        }
        .splash-screen__wordmark {
          font-size: 24px;
          font-weight: 600;
          color: var(--fg, #e8e8e8);
          letter-spacing: -0.02em;
        }
        .splash-screen[data-theme="light"] .splash-screen__wordmark {
          color: #1a1a2e;
        }
        @keyframes float {
          0%, 100% {
            transform: translateY(0);
          }
          50% {
            transform: translateY(-8px);
          }
        }
        @media (prefers-reduced-motion: reduce) {
          .splash-screen__mascot {
            animation: none !important;
          }
        }
      `}</style>
    </div>
  );
}