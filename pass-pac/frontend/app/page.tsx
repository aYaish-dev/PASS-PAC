import Link from "next/link";

const stats = [
  { label: "Total Sessions", value: "0" },
  { label: "Cards Detected", value: "0" },
  { label: "High Risk Findings", value: "0" },
  { label: "Current Mode", value: "Simulator" },
];

export default function Home() {
  return (
    <main className="min-h-screen bg-[#f6f7f9]">
      <section className="mx-auto flex min-h-screen w-full max-w-7xl flex-col px-6 py-8 lg:px-10">
        <header className="flex flex-col border-b border-[#d8dde3] pb-6 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[#2f6f73]">
              Local-first assessment workspace
            </p>
            <h1 className="mt-3 text-3xl font-semibold text-[#17202a] sm:text-4xl">
              PASS-PAC Local Dashboard
            </h1>
          </div>
          <div className="mt-5 inline-flex w-fit items-center gap-2 rounded-md border border-[#b7c3cc] bg-white px-3 py-2 text-sm font-medium text-[#36454f] sm:mt-0">
            <span className="h-2.5 w-2.5 rounded-full bg-[#2f9e44]" />
            Simulator mode
          </div>
        </header>

        <div className="grid gap-4 py-8 sm:grid-cols-2 xl:grid-cols-4">
          {stats.map((stat) => (
            <article
              key={stat.label}
              className="rounded-lg border border-[#d8dde3] bg-white p-5 shadow-sm"
            >
              <p className="text-sm font-medium text-[#52616b]">{stat.label}</p>
              <p className="mt-4 text-3xl font-semibold text-[#17202a]">
                {stat.value}
              </p>
            </article>
          ))}
        </div>

        <section className="grid flex-1 gap-4 lg:grid-cols-[1.5fr_1fr]">
          <div className="rounded-lg border border-[#d8dde3] bg-white p-6 shadow-sm">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <h2 className="text-lg font-semibold text-[#17202a]">
                Assessment Sessions
              </h2>
              <Link
                href="/sessions"
                className="inline-flex w-fit items-center justify-center rounded-md bg-[#2f6f73] px-4 py-2 text-sm font-semibold text-white transition hover:bg-[#255b5f] focus:outline-none focus:ring-2 focus:ring-[#2f6f73] focus:ring-offset-2"
              >
                Manage Sessions
              </Link>
            </div>
            <div className="mt-6 flex min-h-56 items-center justify-center rounded-md border border-dashed border-[#b7c3cc] bg-[#fafbfc] text-sm font-medium text-[#6b7780]">
              No sessions yet
            </div>
          </div>

          <aside className="rounded-lg border border-[#d8dde3] bg-white p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-[#17202a]">
              Local Resources
            </h2>
            <dl className="mt-5 space-y-4 text-sm">
              <div className="flex items-center justify-between gap-4 border-b border-[#edf0f2] pb-3">
                <dt className="font-medium text-[#52616b]">Reports</dt>
                <dd className="text-[#17202a]">Local folder</dd>
              </div>
              <div className="flex items-center justify-between gap-4 border-b border-[#edf0f2] pb-3">
                <dt className="font-medium text-[#52616b]">Mock data</dt>
                <dd className="text-[#17202a]">Simulator ready</dd>
              </div>
              <div className="flex items-center justify-between gap-4">
                <dt className="font-medium text-[#52616b]">Proxmark</dt>
                <dd className="text-[#17202a]">Placeholder only</dd>
              </div>
            </dl>
          </aside>
        </section>
      </section>
    </main>
  );
}
