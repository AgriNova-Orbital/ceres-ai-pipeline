"use client";

import { useEffect } from "react";
import { applyTheme, getStoredThemeSafe } from "@/lib/theme";

export default function ThemeBoot() {
  useEffect(() => {
    applyTheme(getStoredThemeSafe());
  }, []);

  return null;
}
