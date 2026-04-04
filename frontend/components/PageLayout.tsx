import Link from "next/link";
import LogoutButton from "@/components/LogoutButton";
import LanguageSwitcher from "@/components/LanguageSwitcher";
import LocaleText from "@/components/LocaleText";

export default function PageLayout({
  title,
  description,
  children,
  actions,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b px-4 sm:px-8 py-4">
        <div className="max-w-4xl mx-auto flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
          <div className="flex items-center gap-4">
            <Link href="/" className="text-primary hover:underline text-sm">
              &larr; <LocaleText k="home" fallback="Home" />
            </Link>
            <h1 className="text-xl font-bold">{title}</h1>
          </div>
          <div className="flex items-center gap-3">
            <LanguageSwitcher />
            {actions}
            <LogoutButton />
          </div>
        </div>
      </header>
      <main className="max-w-4xl mx-auto px-4 sm:px-8 py-6 space-y-6">
        {description && (
          <p className="text-sm text-gray-600">{description}</p>
        )}
        {children}
      </main>
    </div>
  );
}
