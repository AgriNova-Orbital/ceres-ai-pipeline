import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Ceres AI Pipeline",
  description: "Wheat Risk WebUI - dual mode + shared LAN workflow",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
