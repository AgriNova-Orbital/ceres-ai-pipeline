import Link from "next/link";

export default function PrivacyPage() {
  return (
    <main className="min-h-screen bg-stone-50 px-4 py-10 text-stone-900 dark:bg-stone-950 dark:text-stone-100">
      <div className="mx-auto max-w-4xl rounded-xl border border-stone-200 bg-white p-6 shadow-sm dark:border-stone-700 dark:bg-stone-900 sm:p-10">
        <header className="border-b border-stone-200 pb-5 dark:border-stone-700">
          <h1 className="text-2xl font-bold sm:text-3xl">Privacy Policy（隱私權政策）</h1>
          <p className="mt-2 text-sm text-stone-600 dark:text-stone-400">Ceres AI / 穀神星AI</p>
          <p className="mt-1 text-xs text-stone-500 dark:text-stone-400">Effective Date: 2026-04-05</p>
        </header>

        <article className="mt-6 space-y-6 text-sm leading-7 sm:text-base">
          <section>
            <h2 className="text-base font-semibold sm:text-lg">1. Scope（適用範圍）</h2>
            <p className="mt-2 text-stone-700 dark:text-stone-300">
              本政策適用於 Ceres AI / 穀神星AI（以下稱「本服務」）之網站、登入流程、資料處理與相關功能。當您使用本服務時，即表示您已閱讀並同意本政策。
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold sm:text-lg">2. Data We Collect（蒐集資訊）</h2>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-stone-700 dark:text-stone-300">
              <li>帳號基本識別資訊（如使用者名稱、登入狀態）。</li>
              <li>您授權之 OAuth 憑證與必要連線資訊（例如 Google OAuth token）。</li>
              <li>任務執行相關技術資料（如工作狀態、錯誤訊息、作業日誌）。</li>
            </ul>
          </section>

          <section>
            <h2 className="text-base font-semibold sm:text-lg">3. Purpose of Use（使用目的）</h2>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-stone-700 dark:text-stone-300">
              <li>提供身份驗證、授權與帳戶安全管理。</li>
              <li>提供資料存取、模型訓練、評估與工作流程管理功能。</li>
              <li>維護平台穩定性、除錯與系統監控。</li>
            </ul>
          </section>

          <section>
            <h2 className="text-base font-semibold sm:text-lg">4. Data Sharing（資料揭露）</h2>
            <p className="mt-2 text-stone-700 dark:text-stone-300">
              除法律要求、主管機關命令，或為提供您要求之功能所必需外，本服務不會任意出售、出租或交換您的個人資料予第三方。
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold sm:text-lg">5. Retention & Security（保存與安全）</h2>
            <p className="mt-2 text-stone-700 dark:text-stone-300">
              我們將在達成前述目的所必要期間內保存資料，並採取合理技術與管理措施降低未經授權存取、竄改或洩漏之風險。
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold sm:text-lg">6. Your Rights（您的權利）</h2>
            <p className="mt-2 text-stone-700 dark:text-stone-300">
              您可依適用法令請求查詢、更正或刪除您的資料；若您希望撤回授權，可透過設定頁面中斷 OAuth 連線，或與我們聯繫。
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold sm:text-lg">7. Policy Updates（政策更新）</h2>
            <p className="mt-2 text-stone-700 dark:text-stone-300">
              本政策可能因法規或服務調整而修訂。若有重大變更，將於本頁更新版本與生效日期。
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold sm:text-lg">8. Contact（聯絡方式）</h2>
            <p className="mt-2 text-stone-700 dark:text-stone-300">
              Email:
              <a className="ml-1 text-emerald-700 hover:underline dark:text-emerald-400" href="mailto:a0903932792@gmail.com">
                a0903932792@gmail.com
              </a>
            </p>
          </section>
        </article>

        <div className="mt-8 flex flex-wrap gap-4 border-t border-stone-200 pt-5 text-sm dark:border-stone-700">
          <Link href="/terms" className="text-emerald-700 hover:underline dark:text-emerald-400">
            Terms of Service（服務條款）
          </Link>
          <Link href="/" className="text-emerald-700 hover:underline dark:text-emerald-400">
            Back to Home（返回首頁）
          </Link>
        </div>
      </div>
    </main>
  );
}
