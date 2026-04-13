import Link from "next/link";

export default function TermsPage() {
  return (
    <main className="min-h-screen bg-stone-50 px-4 py-10 text-stone-900 dark:bg-stone-950 dark:text-stone-100">
      <div className="mx-auto max-w-4xl rounded-xl border border-stone-200 bg-white p-6 shadow-sm dark:border-stone-700 dark:bg-stone-900 sm:p-10">
        <header className="border-b border-stone-200 pb-5 dark:border-stone-700">
          <h1 className="text-2xl font-bold sm:text-3xl">Terms of Service（服務條款）</h1>
          <p className="mt-2 text-sm text-stone-600 dark:text-stone-400">Ceres AI / 穀神星AI</p>
          <p className="mt-1 text-xs text-stone-500 dark:text-stone-400">Effective Date: 2026-04-05</p>
        </header>

        <article className="mt-6 space-y-6 text-sm leading-7 sm:text-base">
          <section>
            <h2 className="text-base font-semibold sm:text-lg">1. Acceptance（條款同意）</h2>
            <p className="mt-2 text-stone-700 dark:text-stone-300">
              使用本服務即表示您同意遵守本條款與相關政策。若您不同意本條款，請停止使用本服務。
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold sm:text-lg">2. Service Description（服務內容）</h2>
            <p className="mt-2 text-stone-700 dark:text-stone-300">
              本服務提供資料處理、工作排程、模型訓練與評估等功能，並可透過 OAuth 與外部服務整合。具體功能可能因版本或維護需求調整。
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold sm:text-lg">3. User Responsibilities（使用者責任）</h2>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-stone-700 dark:text-stone-300">
              <li>您應確保使用本服務之行為符合適用法律與授權範圍。</li>
              <li>您應妥善保管帳號與授權資訊，避免未經授權之存取。</li>
              <li>您不得利用本服務從事破壞性、非法或侵權活動。</li>
            </ul>
          </section>

          <section>
            <h2 className="text-base font-semibold sm:text-lg">4. Availability（服務可用性）</h2>
            <p className="mt-2 text-stone-700 dark:text-stone-300">
              我們將盡力維持服務穩定，但不保證服務永不中斷。因維護、更新、網路或第三方服務異常所造成之中斷，可能導致短暫不可用。
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold sm:text-lg">5. Limitation of Liability（責任限制）</h2>
            <p className="mt-2 text-stone-700 dark:text-stone-300">
              在法律允許範圍內，本服務對於因使用或無法使用本服務所衍生之間接、附帶或衍生性損害，不負賠償責任。使用者應自行評估與承擔業務決策風險。
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold sm:text-lg">6. Termination（終止）</h2>
            <p className="mt-2 text-stone-700 dark:text-stone-300">
              若發現違反本條款、濫用系統或危及平台安全之行為，我們得暫停或終止您的使用權限。
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold sm:text-lg">7. Changes to Terms（條款修訂）</h2>
            <p className="mt-2 text-stone-700 dark:text-stone-300">
              我們得視營運或法規需求更新本條款。更新後版本將公告於本頁，並以更新後條款為準。
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
          <Link href="/privacy" className="text-emerald-700 hover:underline dark:text-emerald-400">
            Privacy Policy（隱私權政策）
          </Link>
          <Link href="/" className="text-emerald-700 hover:underline dark:text-emerald-400">
            Back to Home（返回首頁）
          </Link>
        </div>
      </div>
    </main>
  );
}
