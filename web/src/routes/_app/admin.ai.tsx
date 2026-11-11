import { useEffect, useState } from 'react'
import { Link, createFileRoute, useNavigate } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { BTN, BTN_PRIMARY, Problem } from '#/components/cv/parts'
import { getAiUsage } from '#/lib/admin-api'
import type { UsageReport } from '#/lib/admin-api'
import {
  count,
  tokens,
  trouble,
  usd,
  windowLabel,
  workflowName,
} from '#/lib/admin-view'
import { useMe } from '#/lib/useMe'

export const Route = createFileRoute('/_app/admin/ai')({
  head: () => ({ meta: [{ title: 'AI cost and quality | Jobmigo' }] }),
  component: AiUsagePage,
})

const CARD = 'rounded-2xl border border-border bg-surface p-5'
const TH = 'px-3 py-2 text-left text-xs font-bold uppercase text-faint'
const TD = 'px-3 py-2 align-top text-sm text-ink'
const WINDOWS = [7, 30, 90] as const

class LoadError extends Error {
  readonly code: string
  constructor(code: string) {
    super(code)
    this.code = code
  }
}

function AiUsagePage() {
  const me = useMe()
  const navigate = useNavigate()
  const [days, setDays] = useState<number>(30)
  const signedOut = me.data?.ok === false && me.data.code === 'unauthorized'
  const staff =
    me.data?.ok === true &&
    (me.data.me.staff?.permissions.includes('overview.read') ?? false)

  useEffect(() => {
    if (signedOut) void navigate({ to: '/sign-in' })
  }, [signedOut, navigate])

  const report = useQuery({
    queryKey: ['ai-usage', days],
    enabled: staff,
    retry: false,
    queryFn: async () => {
      const result = await getAiUsage(days)
      if (!result.ok) throw new LoadError(result.code)
      return result.data
    },
  })

  if (me.isPending || signedOut) {
    return (
      <div
        aria-busy="true"
        aria-label="Loading"
        className="mx-auto max-w-[960px] animate-pulse"
      >
        <div className="h-9 w-1/3 rounded-md bg-surface-sunken" />
        <div className="mt-6 h-40 rounded-2xl bg-surface-sunken" />
      </div>
    )
  }

  if (!staff) {
    return (
      <div className="mx-auto flex max-w-[720px] flex-col gap-3">
        <Problem
          title="This page is for staff"
          body="It shows what the AI calls cost. Your account has no staff role, so there is nothing to show here."
        >
          <Link to="/settings" className={BTN}>
            Back to Settings
          </Link>
        </Problem>
      </div>
    )
  }

  return (
    <div className="mx-auto flex w-full max-w-[960px] flex-col gap-6">
      <header>
        <h1 className="font-display text-[28px] font-bold tracking-tight text-ink">
          AI cost and quality
        </h1>
        <p className="mt-1.5 text-sm text-faint">
          Read-only. Counts, tokens and money from the usage ledger, for every
          account on this install. It holds no posting, profile or model text.
        </p>
      </header>

      <div role="group" aria-label="Time window" className="flex gap-2">
        {WINDOWS.map((w) => (
          <button
            key={w}
            type="button"
            aria-pressed={days === w}
            className={days === w ? BTN_PRIMARY : BTN}
            onClick={() => setDays(w)}
          >
            {windowLabel(w)}
          </button>
        ))}
      </div>

      {report.isPending ? (
        <div
          aria-busy="true"
          aria-label="Loading the report"
          className="animate-pulse"
        >
          <div className="h-40 rounded-2xl bg-surface-sunken" />
        </div>
      ) : report.isError ? (
        <Problem
          title="We could not load the report"
          body={
            report.error instanceof LoadError &&
            report.error.code === 'forbidden'
              ? 'Your account is not allowed to read it.'
              : 'Try again in a moment. Nothing changed.'
          }
        >
          <button
            type="button"
            className={BTN_PRIMARY}
            disabled={report.isFetching}
            onClick={() => void report.refetch()}
          >
            {report.isFetching ? 'Retrying…' : 'Retry'}
          </button>
        </Problem>
      ) : (
        <Report data={report.data} />
      )}
    </div>
  )
}

function Tile({
  label,
  value,
  note,
}: {
  label: string
  value: string
  note?: string
}) {
  return (
    <div className={CARD}>
      <p className="text-xs font-bold uppercase text-faint">{label}</p>
      <p className="mt-1 font-display text-2xl font-bold text-ink">{value}</p>
      {note ? <p className="mt-1 text-[13px] text-muted">{note}</p> : null}
    </div>
  )
}

function Report({ data }: { data: UsageReport }) {
  if (data.rows.length === 0) {
    return (
      <div className={CARD}>
        <h2 className="font-display text-lg font-bold text-ink">
          No AI calls in the last {windowLabel(data.days)}
        </h2>
        <p className="mt-1 text-sm text-muted">
          Calls appear here once a CV is read, a job is screened or a fit check
          is run.
        </p>
      </div>
    )
  }
  const calls = data.workflows.reduce((n, w) => n + w.calls, 0)
  const rejected = data.workflows.reduce((n, w) => n + w.rejected, 0)
  const failed = data.workflows.reduce((n, w) => n + w.failed, 0)
  const share = trouble(calls, rejected, failed)

  return (
    <>
      <section
        aria-label="Summary"
        className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"
      >
        <Tile
          label={`Cost, ${windowLabel(data.days)}`}
          value={usd(data.totalCostUsd)}
          note={
            data.unknownCostCalls > 0
              ? `${count(data.unknownCostCalls)} calls have no price set, so they are not in this total.`
              : 'Every call has a price.'
          }
        />
        <Tile label="Calls to the model" value={count(calls)} />
        <Tile
          label="No usable answer"
          value={share === null ? 'None' : `${share}%`}
          note={`${count(rejected)} rejected, ${count(failed)} failed.`}
        />
        <Tile
          label="Saved by the cache"
          value={usd(data.cacheSavingsUsd)}
          note="An estimate: cache hits at the average cost of a call."
        />
      </section>

      <section aria-labelledby="by-workflow" className={CARD}>
        <h2
          id="by-workflow"
          className="font-display text-lg font-bold text-ink"
        >
          By workflow
        </h2>
        <p className="mt-1 text-sm text-muted">
          Average cost is per call that gave a usable answer and had a price.
          Screening and the fit check are separate rows.
        </p>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[640px] border-collapse">
            <thead>
              <tr>
                <th className={TH}>Workflow</th>
                <th className={TH}>Calls</th>
                <th className={TH}>Cache hits</th>
                <th className={TH}>Rejected</th>
                <th className={TH}>Failed</th>
                <th className={TH}>Tokens in / out</th>
                <th className={TH}>Cost</th>
                <th className={TH}>Per call</th>
              </tr>
            </thead>
            <tbody>
              {data.workflows.map((w) => (
                <tr key={w.workflow} className="border-t border-surface-sunken">
                  <th scope="row" className={`${TD} font-bold`}>
                    {workflowName(w.workflow)}
                  </th>
                  <td className={TD}>{count(w.calls)}</td>
                  <td className={TD}>{count(w.cacheHits)}</td>
                  <td className={TD}>{count(w.rejected)}</td>
                  <td className={TD}>{count(w.failed)}</td>
                  <td className={TD}>
                    {tokens(w.tokensIn)} / {tokens(w.tokensOut)}
                  </td>
                  <td className={TD}>{usd(w.costUsd)}</td>
                  <td className={TD}>{usd(w.avgCostUsd)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section aria-labelledby="by-version" className={CARD}>
        <h2 id="by-version" className="font-display text-lg font-bold text-ink">
          By model and prompt version
        </h2>
        <p className="mt-1 text-sm text-muted">
          Compare these rows before and after a model or prompt change.
        </p>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[640px] border-collapse">
            <thead>
              <tr>
                <th className={TH}>Workflow</th>
                <th className={TH}>Model</th>
                <th className={TH}>Prompt</th>
                <th className={TH}>Calls</th>
                <th className={TH}>Rejected / failed</th>
                <th className={TH}>Cost</th>
                <th className={TH}>Per call</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((r) => (
                <tr
                  key={`${r.workflow}|${r.provider}|${r.model}|${r.promptVersion}`}
                  className="border-t border-surface-sunken"
                >
                  <th scope="row" className={`${TD} font-bold`}>
                    {workflowName(r.workflow)}
                  </th>
                  <td className={`${TD} break-all`}>
                    {r.provider}/{r.model}
                  </td>
                  <td className={`${TD} break-all`}>{r.promptVersion}</td>
                  <td className={TD}>{count(r.calls)}</td>
                  <td className={TD}>
                    {count(r.rejected)} / {count(r.failed)}
                  </td>
                  <td className={TD}>{usd(r.costUsd)}</td>
                  <td className={TD}>{usd(r.avgCostUsd)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <div className="grid gap-3 md:grid-cols-2">
        <section aria-labelledby="paid" className={CARD}>
          <h2 id="paid" className="font-display text-lg font-bold text-ink">
            The same usage on {data.compare.label}
          </h2>
          {data.compare.configured ? (
            <>
              <p className="mt-1 font-display text-2xl font-bold text-ink">
                {usd(data.compare.estimateUsd)}
              </p>
              <p className="mt-1 text-[13px] text-muted">
                An estimate from the tokens above at the price you set. Cache
                hits are not counted.
              </p>
            </>
          ) : (
            <p className="mt-1 text-sm text-muted">
              Not set. Add <code>AI_COMPARE_PRICE</code> to <code>.env</code> as
              input and output dollars per million tokens, for example{' '}
              <code>3,15</code>, and an optional <code>AI_COMPARE_LABEL</code>.
              No price is guessed.
            </p>
          )}
        </section>
        <section aria-labelledby="golden" className={CARD}>
          <h2 id="golden" className="font-display text-lg font-bold text-ink">
            Golden set
          </h2>
          <p className="mt-1 text-sm text-muted">
            Not run yet. The golden set comes with the evaluation checks. When
            it exists, its match rate shows here beside what that run cost.
          </p>
        </section>
      </div>
    </>
  )
}
