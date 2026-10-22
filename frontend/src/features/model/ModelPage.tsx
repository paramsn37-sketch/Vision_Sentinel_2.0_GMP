import {
  Panel,
  EmptyState,
  ErrorState,
  Metric,
  Skeleton,
  StatusPill,
  Table,
  Td,
  Th,
  Tr,
} from '@/components/ui'
import { url } from '@/lib/api/client'
import { useActiveModel, useDataset, useEvaluations, useFigures, useRuns } from '@/lib/api/hooks'
import { absoluteTime, pct } from '@/lib/format'

/** Everything about the detector, from files the build wrote (registry, eval JSON, figures). Nothing invented:
 *  anything not yet measured says so. */
export default function ModelPage() {
  const model = useActiveModel()
  const evals = useEvaluations()
  const runs = useRuns()
  const figures = useFigures()
  const dataset = useDataset()
  const m = model.data
  const counting = evals.data?.counting
  const xai = evals.data?.xai
  const detector = evals.data?.detector
  const latency = evals.data?.latency
  const activeEval = detector?.models.find((d) => d.name === detector.active)
  const baselines = detector?.models.filter((d) => d.name !== detector.active) ?? []
  const num = (v: number | null | undefined, digits = 3) => (v == null ? '—' : v.toFixed(digits))

  const mean = (k: 'naive_1fps' | 'bytetrack_default' | 'ours') =>
    counting ? counting.report.reduce((a, r) => a + r[k].count_error, 0) / counting.report.length : null

  return (
    <div className="flex flex-col gap-4 p-4">
      <h1 className="text-xl">Model</h1>
      <Panel title="Active model" bodyClassName="p-4">
        {model.isPending ? (
          <Skeleton className="h-16" />
        ) : model.isError ? (
          <ErrorState error={model.error} />
        ) : !m?.loaded ? (
          <EmptyState title="No model loaded">
            {m?.error ?? 'The detector failed to load. Check the server log.'}
          </EmptyState>
        ) : (
          <div className="flex flex-col gap-4">
            <div className="grid grid-cols-2 gap-6 md:grid-cols-5">
              <Metric label="Name" value={<span className="font-sans text-lg">{m.name}</span>} />
              <Metric label="Input size" value={m.imgsz} unit="px" />
              <Metric label="Device" value={<span className="font-sans text-lg">{m.device}</span>} />
              <Metric label="Classes" value={m.classes?.length ?? 0} />
              <Metric
                label="PPE model"
                value={<span className="font-sans text-lg">{m.is_ppe_model ? 'Yes' : 'No'}</span>}
                note={m.is_ppe_model ? undefined : 'persons only until the trained model is installed'}
              />
            </div>
            <div className="flex flex-wrap gap-1.5">
              {m.classes?.map((c) => (
                <StatusPill key={c} tone="neutral">
                  {c}
                  {m.thresholds?.[c] !== undefined && (
                    <span className="num ml-1 text-subtle">≥{m.thresholds[c].toFixed(2)}</span>
                  )}
                </StatusPill>
              ))}
            </div>
          </div>
        )}
      </Panel>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Panel title="Detector accuracy (held-out test split)" bodyClassName="overflow-x-auto">
          {activeEval?.per_class.length ? (
            <div className="flex flex-col">
              <Table>
                <thead>
                  <tr>
                    <Th>Class</Th>
                    <Th align="right">Precision</Th>
                    <Th align="right">Recall</Th>
                    <Th align="right">mAP50</Th>
                    <Th align="right">mAP50-95</Th>
                  </tr>
                </thead>
                <tbody>
                  {activeEval.per_class.map((r) => (
                    <Tr key={r.class}>
                      <Td className="text-fg">{r.class}</Td>
                      <Td align="right">{num(r.precision)}</Td>
                      <Td align="right">{num(r.recall)}</Td>
                      <Td align="right">{num(r.map50)}</Td>
                      <Td align="right">{num(r.map50_95)}</Td>
                    </Tr>
                  ))}
                  <Tr>
                    <Td className="font-semibold text-fg">mean</Td>
                    <Td />
                    <Td />
                    <Td align="right" className="font-semibold">
                      {num(activeEval.mean.map50)}
                    </Td>
                    <Td align="right">{num(activeEval.mean.map50_95)}</Td>
                  </Tr>
                </tbody>
              </Table>
              {baselines.length > 0 && (
                <p className="px-4 py-3 text-xs text-muted">
                  Person mAP50 on the same split:{' '}
                  {baselines
                    .map((b) => `${b.name} ${num(b.per_class.find((c) => c.class === 'person')?.map50)}`)
                    .join(' · ')}
                  {' · '}this model {num(activeEval.per_class.find((c) => c.class === 'person')?.map50)}. The
                  baselines detect no PPE.
                </p>
              )}
            </div>
          ) : (
            <EmptyState title="Not measured yet">
              The trained model is evaluated on the frozen test split when training finishes
              (docs/eval/detector_results.json).
            </EmptyState>
          )}
        </Panel>
        <Panel title="Unique-person counting (MOT17, held-out sequences)" bodyClassName="p-4">
          {counting ? (
            <div className="flex flex-col gap-4">
              <div className="grid grid-cols-3 gap-4">
                <Metric
                  label="v1 method (per frame, 1/s)"
                  value={pct(mean('naive_1fps'))}
                  note="mean count error"
                />
                <Metric
                  label="ByteTrack defaults"
                  value={pct(mean('bytetrack_default'))}
                  note="mean count error"
                />
                <Metric
                  label="Vision Sentinel 2.0"
                  value={pct(mean('ours'))}
                  note="mean count error"
                  tone={
                    (mean('ours') ?? 1) <= Math.min(mean('naive_1fps') ?? 1, mean('bytetrack_default') ?? 1)
                      ? 'ok'
                      : 'warning'
                  }
                />
              </div>
              <p className="text-xs text-muted">
                Detector {counting.detector} at {counting.imgsz} px; thresholds tuned on MOT17-02/04 (
                {counting.trials} trials). Full report: docs/eval/counting_report.md.
              </p>
            </div>
          ) : (
            <EmptyState title="Not measured yet">Run make eval.</EmptyState>
          )}
        </Panel>
        <Panel title="Explanation checks" bodyClassName="p-4">
          {xai ? (
            <div className="flex flex-col gap-4">
              <div className="grid grid-cols-3 gap-4">
                <Metric
                  label="Pointing game"
                  value={xai.pointing_game == null ? '—' : pct(xai.pointing_game)}
                  note="peak inside the box"
                />
                <Metric
                  label="Deletion check"
                  value={xai.deletion_top_beats_random == null ? '—' : pct(xai.deletion_top_beats_random)}
                  note="hot region beats random"
                />
                <Metric
                  label="Randomisation"
                  value={num(xai.randomisation_ssim, 2)}
                  note={
                    xai.randomisation_ssim == null
                      ? 'not measured'
                      : xai.randomisation_ssim < 0.5
                        ? 'SSIM, pass (< 0.5)'
                        : 'SSIM, fail (needs < 0.5)'
                  }
                  tone={
                    xai.randomisation_ssim != null && xai.randomisation_ssim >= 0.5 ? 'warning' : undefined
                  }
                />
              </div>
              <p className="text-xs text-muted">
                {xai.method} on {xai.samples} test detections with {xai.model}; {num(xai.latency_p50_ms, 0)}{' '}
                ms per explanation (p50, CPU). Full report: docs/eval/xai_report.md.
              </p>
            </div>
          ) : (
            <EmptyState title="Not measured yet">
              Pointing game, deletion and randomisation checks are written to docs/eval/xai_report.md.
            </EmptyState>
          )}
        </Panel>
        <Panel title="Speed" bodyClassName="p-4">
          {latency?.length ? (
            <Table>
              <thead>
                <tr>
                  <Th>Model</Th>
                  <Th>Runtime</Th>
                  <Th align="right">Input</Th>
                  <Th align="right">p50</Th>
                  <Th align="right">p95</Th>
                </tr>
              </thead>
              <tbody>
                {latency.map((v) => (
                  <Tr key={`${v.model}-${v.runtime}-${v.imgsz}`}>
                    <Td className="text-fg">{v.model}</Td>
                    <Td className="text-muted">
                      {v.runtime} · {v.device ?? 'cpu'}
                    </Td>
                    <Td align="right">{v.imgsz} px</Td>
                    <Td align="right">{v.p50_ms.toFixed(0)} ms</Td>
                    <Td align="right">{v.p95_ms.toFixed(0)} ms</Td>
                  </Tr>
                ))}
              </tbody>
            </Table>
          ) : (
            <EmptyState title="Not measured yet">
              Latency is benchmarked on this machine after training (training/benchmarks/latency.json).
            </EmptyState>
          )}
        </Panel>
      </div>

      <Panel title="Training runs" bodyClassName="overflow-x-auto">
        {runs.isPending ? (
          <Skeleton className="m-4 h-12" />
        ) : !runs.data?.runs.length ? (
          <EmptyState title="No training runs recorded">
            training/registry.json lists every run with its data manifest and environment.
          </EmptyState>
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>Run</Th>
                <Th>Base model</Th>
                <Th>Status</Th>
                <Th align="right">Image size</Th>
                <Th align="right">Epochs</Th>
                <Th align="right">Val mAP50</Th>
                <Th align="right">Test person mAP50</Th>
                <Th align="right">Started</Th>
              </tr>
            </thead>
            <tbody>
              {runs.data.runs.map((run) => (
                <Tr key={run.id}>
                  <Td className="text-fg">
                    {run.id}
                    {run.note && <div className="text-xs text-muted">{run.note}</div>}
                  </Td>
                  <Td className="text-muted">{run.model}</Td>
                  <Td>
                    <StatusPill
                      tone={
                        run.status === 'trained'
                          ? 'ok'
                          : run.status === 'running'
                            ? 'info'
                            : run.status === 'interrupted'
                              ? 'warning'
                              : 'neutral'
                      }
                    >
                      {run.status}
                    </StatusPill>
                  </Td>
                  <Td align="right">{run.imgsz ?? '—'}</Td>
                  <Td align="right">{run.epochs_completed ?? '—'}</Td>
                  <Td align="right">{num(run.val_map50)}</Td>
                  <Td align="right">{num(run.test_person_map50)}</Td>
                  <Td align="right" className="text-muted">
                    {absoluteTime(run.created_at)}
                  </Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        )}
      </Panel>

      <Panel title="Figures" bodyClassName="p-4">
        {figures.isPending ? (
          <Skeleton className="h-32" />
        ) : (
          <div className="flex flex-col gap-6">
            {Object.entries(figures.data ?? {}).map(([group, names]) =>
              names.length ? (
                <div key={group}>
                  <h3 className="mb-2 text-sm font-semibold capitalize">{group}</h3>
                  <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
                    {names.map((n) => (
                      <figure key={n} className="flex flex-col gap-1">
                        <a href={url(`/model/figures/${group}/${n}`)} target="_blank" rel="noreferrer">
                          <img
                            src={url(`/model/figures/${group}/${n}`)}
                            alt={n.replace(/[_-]/g, ' ').replace(/\.\w+$/, '')}
                            loading="lazy"
                            className="w-full rounded-sm border border-line bg-white"
                          />
                        </a>
                        <figcaption className="text-xs text-muted">{n}</figcaption>
                      </figure>
                    ))}
                  </div>
                </div>
              ) : null,
            )}
          </div>
        )}
      </Panel>

      <Panel title="Dataset card" bodyClassName="p-4">
        {dataset.data?.card ? (
          <details>
            <summary className="cursor-pointer text-sm text-accent">Show data/DATASET_CARD.md</summary>
            <pre className="mt-3 max-h-[480px] overflow-auto text-xs leading-relaxed whitespace-pre-wrap text-muted">
              {dataset.data.card}
            </pre>
          </details>
        ) : (
          <p className="text-sm text-muted">No dataset card found.</p>
        )}
      </Panel>
    </div>
  )
}
