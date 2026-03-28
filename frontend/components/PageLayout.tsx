import Link from "next/link";
import LogoutButton from "@/components/LogoutButton";

export default function PageLayout({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen p-8">
      <header className="mb-8 flex justify-between items-center">
        <div className="flex items-center gap-4">
          <Link href="/" className="text-primary hover:underline">&larr; Home</Link>
          <h1 className="text-2xl font-bold">{title}</h1>
        </div>
        <LogoutButton />
      </header>
      <main className="max-w-4xl mx-auto">{children}</main>
    </div>
  );
}
