"use client";
import { useEffect, useState } from "react";
/** 深色／淺色切換（記在 localStorage） */
export default function ThemeToggle() {
  const [light, setLight] = useState(false);
  useEffect(() => { setLight(document.documentElement.classList.contains("light")); }, []);
  const flip = () => {
    const next = !light; setLight(next);
    const el = document.documentElement; el.classList.toggle("light", next); el.classList.toggle("dark", !next);
    try { localStorage.setItem("theme", next ? "light" : "dark"); } catch { /* 無法儲存時忽略 */ }
  };
  return <button className="btn" onClick={flip} aria-label="切換深色／淺色">{light ? "🌙 深色" : "☀️ 淺色"}</button>;
}
