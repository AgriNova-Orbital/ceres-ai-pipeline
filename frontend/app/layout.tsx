import type { Metadata } from "next";
import "./globals.css";
import ThemeBoot from "@/components/ThemeBoot";

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
  return (
    <html lang="en">
      <body>
        <ThemeBoot />
        {children}
      </body>
    </html>
  );
}
