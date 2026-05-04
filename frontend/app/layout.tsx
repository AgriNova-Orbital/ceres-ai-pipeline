import type { Metadata } from "next";
import "./globals.css";
import { ClerkProvider } from "@clerk/nextjs";
import ThemeBoot from "@/components/ThemeBoot";
import ClerkAuthControls from "@/components/ClerkAuthControls";

export const metadata: Metadata = {
  title: "Ceres AI Pipeline",
  description: "Wheat Risk WebUI - dual mode + shared LAN workflow",
  icons: {
    icon: "/logo/favicon.png",
    shortcut: "/logo/favicon.png",
    apple: "/logo/favicon.png",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const clerkPublishableKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

  return (
    <html lang="en">
      <body>
        {clerkPublishableKey ? (
          <ClerkProvider publishableKey={clerkPublishableKey}>
            <ThemeBoot />
            <ClerkAuthControls />
            {children}
          </ClerkProvider>
        ) : (
          <>
            <ThemeBoot />
            {children}
          </>
        )}
      </body>
    </html>
  );
}
