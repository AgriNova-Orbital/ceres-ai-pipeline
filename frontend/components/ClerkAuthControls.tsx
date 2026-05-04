"use client";

import type { ReactNode } from "react";
import { SignInButton, SignUpButton, UserButton, useAuth } from "@clerk/nextjs";

function Show({
  when,
  children,
}: {
  when: "signed-in" | "signed-out";
  children: ReactNode;
}) {
  const { isLoaded, isSignedIn } = useAuth();

  if (!isLoaded) {
    return null;
  }

  if (when === "signed-in" && isSignedIn) {
    return <>{children}</>;
  }

  if (when === "signed-out" && !isSignedIn) {
    return <>{children}</>;
  }

  return null;
}

export default function ClerkAuthControls() {
  return (
    <div className="fixed right-4 top-4 z-50 flex items-center gap-2 rounded-full border border-white/20 bg-slate-950/75 px-3 py-2 text-sm text-white shadow-lg backdrop-blur">
      <Show when="signed-out">
        <SignInButton mode="modal">
          <button className="rounded-full px-3 py-1.5 hover:bg-white/10" type="button">
            Sign in
          </button>
        </SignInButton>
        <SignUpButton mode="modal">
          <button className="rounded-full bg-white px-3 py-1.5 font-medium text-slate-950 hover:bg-slate-200" type="button">
            Sign up
          </button>
        </SignUpButton>
      </Show>
      <Show when="signed-in">
        <UserButton />
      </Show>
    </div>
  );
}
