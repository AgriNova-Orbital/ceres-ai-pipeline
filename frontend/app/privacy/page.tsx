import Link from "next/link";

export default function PrivacyPage() {
  return (
    <main className="min-h-screen bg-gray-50 px-4 py-10">
      <div className="mx-auto max-w-3xl rounded-lg border bg-white p-6 sm:p-8">
        <h1 className="text-2xl font-bold text-gray-900">Privacy Policy</h1>
        <p className="mt-2 text-sm text-gray-500">Ceres AI / 穀神星AI</p>

        <section className="mt-8 space-y-4 text-sm leading-7 text-gray-700">
          <h2 className="text-base font-semibold text-gray-900">Data Collection</h2>
          <p>我們僅在提供服務所需範圍內蒐集必要資訊，例如帳號識別資料與您授權的 Google OAuth 存取權杖。</p>

          <h2 className="text-base font-semibold text-gray-900">Data Usage</h2>
          <p>蒐集之資料僅用於身份驗證、Google Drive 連線與系統功能運作，不會出售或出租給第三方。</p>

          <h2 className="text-base font-semibold text-gray-900">Contact</h2>
          <p>
            若您對隱私權政策有任何問題，請聯絡：
            <a className="ml-1 text-primary hover:underline" href="mailto:a0903932792@gmail.com">
              a0903932792@gmail.com
            </a>
          </p>
        </section>

        <div className="mt-8 flex flex-wrap gap-4 text-sm">
          <Link href="/terms" className="text-primary hover:underline">
            查看服務條款 / Terms of Service
          </Link>
          <Link href="/" className="text-primary hover:underline">
            返回首頁 / Back to Home
          </Link>
        </div>
      </div>
    </main>
  );
}
