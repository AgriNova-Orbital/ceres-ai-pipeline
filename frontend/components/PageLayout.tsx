import Link from "next/link";
import LogoutButton from "@/components/LogoutButton";
import LanguageSwitcher from "@/components/LanguageSwitcher";
import ThemeSwitcher from "@/components/ThemeSwitcher";
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
    <div className="min-h-screen bg-stone-50 text-stone-900 dark:bg-stone-950 dark:text-stone-100">
      <header className="border-b border-stone-200 bg-white px-4 py-4 dark:border-stone-800 dark:bg-stone-900 sm:px-8">
        <div className="max-w-4xl mx-auto flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
          <div className="flex items-center gap-4">
            <Link href="/dashboard" className="text-sm text-emerald-700 hover:underline dark:text-emerald-400">
              &larr; <LocaleText k="home" fallback="Home" />
            </Link>
            <h1 className="text-xl font-bold text-stone-900 dark:text-stone-100">{title}</h1>
          </div>
          <div className="flex items-center gap-3">
            <ThemeSwitcher />
            <LanguageSwitcher />
            {actions}
            <LogoutButton />
          </div>
        </div>
      </header>
      <main className="max-w-4xl mx-auto px-4 sm:px-8 py-6 space-y-6">
        {description && (
          <p className="text-sm text-stone-600 dark:text-stone-400">{description}</p>
        )}
        {children}
      </main>
    </div>
  );
}
