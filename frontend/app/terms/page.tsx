import Link from "next/link";

export default function TermsPage() {
  return (
    <main className="min-h-screen bg-gray-50 px-4 py-10">
      <div className="mx-auto max-w-3xl rounded-lg border bg-white p-6 sm:p-8">
        <h1 className="text-2xl font-bold text-gray-900">Terms of Service</h1>
        <p className="mt-2 text-sm text-gray-500">Ceres AI / 穀神星AI</p>

        <section className="mt-8 space-y-4 text-sm leading-7 text-gray-700">
          <h2 className="text-base font-semibold text-gray-900">Service Scope</h2>
          <p>本服務提供資料處理與 OAuth 整合功能。您同意僅在合法且授權範圍內使用本平台。</p>

          <h2 className="text-base font-semibold text-gray-900">User Responsibility</h2>
          <p>您需自行保管帳號與授權資訊，並對使用行為負責。如有未經授權使用情形，請立即通知我們。</p>

          <h2 className="text-base font-semibold text-gray-900">Contact</h2>
          <p>
            如對本條款有疑問，請聯絡：
            <a className="ml-1 text-primary hover:underline" href="mailto:a0903932792@gmail.com">
              a0903932792@gmail.com
            </a>
          </p>
        </section>

        <div className="mt-8 flex flex-wrap gap-4 text-sm">
          <Link href="/privacy" className="text-primary hover:underline">
            查看隱私權政策 / Privacy Policy
          </Link>
          <Link href="/" className="text-primary hover:underline">
            返回首頁 / Back to Home
          </Link>
        </div>
      </div>
    </main>
  );
}
