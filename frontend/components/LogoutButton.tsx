"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export default function LogoutButton() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  async function handleLogout() {
    setLoading(true);
    await fetch("/api/auth/logout", { method: "POST" });
    router.push("/login");
    router.refresh();
  }

  return (
    <button
      onClick={handleLogout}
      disabled={loading}
      className="px-4 py-2 text-sm border border-gray-300 rounded-md hover:bg-gray-100 disabled:opacity-50"
    >
      {loading ? "Logging out..." : "Logout"}
    </button>
  );
}
