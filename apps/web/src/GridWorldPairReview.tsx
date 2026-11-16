import { useEffect, useRef, useState } from 'react';
import { readApi } from './apiClient';
import {
  gridWorldReviewListSchema, gridWorldReviewSchema, type EpisodeArtifact,
  type GridWorldComparisonRow, type GridWorldReview, type ModelOption,
} from './apiContracts';

const endpoint = '/api/v1/gridworld-comparison-reviews';
const assessments = { a: '倾向 A 局', b: '倾向 B 局', tradeoff: '各有取舍', insufficient: '证据不足' };
const failures = {
  JUDGE_PROVIDER_ERROR: '评审模型请求失败。',
  JUDGE_REQUEST_TIMEOUT: '评审模型请求超时。等待模型响应的时间已达到上限。',
  INVALID_JUDGE_OUTPUT: '评审模型的输出截断或格式无效。',
  INVALID_EVENT_REFERENCE: '评审引用与两局公开轨迹不符。',
};

export function GridWorldPairReview({ rows: [a, b], artifacts, models }: {
  rows: [GridWorldComparisonRow, GridWorldComparisonRow];
  artifacts: [EpisodeArtifact, EpisodeArtifact] | null;
  models: ModelOption[];
}) {
  const [open, setOpen] = useState(false);
  const [reviews, setReviews] = useState<GridWorldReview[]>([]);
  const [skipped, setSkipped] = useState(0);
  const [loading, setLoading] = useState(false);
  const [ready, setReady] = useState(false);
  const [readFailed, setReadFailed] = useState(false);
  const [revision, setRevision] = useState(0);
  const [judge, setJudge] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const submission = useRef<AbortController | null>(null);
  useEffect(() => () => submission.current?.abort(), []);

  const pairA = a.episode_id;
  const pairB = b.episode_id;
  const key = a.comparison_key;
  useEffect(() => {
    if (!open || ready) return;
    const controller = new AbortController();
    const query = new URLSearchParams({ episode_a: pairA, episode_b: pairB });
    setLoading(true);
    setReadFailed(false);
    void fetch(`${endpoint}?${query}`, { signal: controller.signal })
      .then(response => readApi(response, gridWorldReviewListSchema))
      .then(data => {
        if (controller.signal.aborted) return;
        if (data.reviews.some(review => review.episode_ids[0] !== pairA
          || review.episode_ids[1] !== pairB || review.comparison_key !== key)) {
          throw new Error('Unexpected review sources');
        }
        setReviews(data.reviews);
        setSkipped(data.skipped_count);
        setLoading(false);
        setReady(true);
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setReadFailed(true);
          setLoading(false);
        }
      });
    return () => controller.abort();
  }, [open, ready, revision, pairA, pairB, key]);

  const candidates = models.filter(model => model.provider === 'aihubmix'
    && ![a.model_id.toLowerCase(), b.model_id.toLowerCase()].includes(model.id.toLowerCase()));
  const hasActions = (a.actions ?? 0) + (b.actions ?? 0) > 0;
  async function submit() {
    if (!ready || submission.current || !artifacts || !hasActions || !candidates.some(model => model.id === judge)) return;
    const controller = new AbortController();
    submission.current = controller;
    setPending(true);
    setError('');
    try {
      const response = await fetch(endpoint, {
        method: 'POST', signal: controller.signal, headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ schema_version: '1.0', episode_ids: [pairA, pairB], judge_model: judge }),
      });
      if (response.status === 400 || response.status === 404 || response.status === 422) {
        await readApi(response, gridWorldReviewSchema).catch((reason: unknown) => {
          if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : '评审请求未通过校验。');
        });
        return;
      }
      const review = await readApi(response, gridWorldReviewSchema);
      if (review.episode_ids[0] !== pairA || review.episode_ids[1] !== pairB
        || review.comparison_key !== key || review.judge_model !== judge) throw new Error('Unexpected review sources');
      if (!controller.signal.aborted) setReviews(current => [review, ...current].slice(0, 20));
    } catch {
      if (!controller.signal.aborted) setError('评审请求未确认完成。可重新读取评审记录。');
    } finally {
      submission.current = null;
      if (!controller.signal.aborted) setPending(false);
    }
  }
  const current = ready && !error ? reviews[0] : undefined;
  const history = current ? reviews.slice(1) : reviews;
  function renderReview(review: GridWorldReview) {
    return <article className="comparison-judge-result" key={review.review_id}>
        <h3>{review.output ? assessments[review.output.assessment] : '评审失败'}</h3>
        <p>{review.judge_model} · <time dateTime={review.created_at}>{new Date(review.created_at).toLocaleString('zh-CN')}</time></p>
        {review.output && <p className="comparison-judge-rationale">{review.output.rationale}</p>}
        {review.prompt_version === 'gridworld-pair-review-v1' && <p className="metric-sub">历史评审 · 初版提示</p>}
        {review.failure_code && <p className="record-failed">{failures[review.failure_code]}</p>}
        {review.output?.citations.length ? <ul className="comparison-citations">
          {review.output.citations.map((citation, index) => {
            const side = citation.side === 'a' ? 0 : 1;
            const source = artifacts?.[side];
            const event = source?.events.find(item => item.event_id === citation.event_id);
            return <li key={`${citation.side}:${citation.event_id}:${index}`}>
              {citation.side.toUpperCase()} 局 · {event ? `第 ${event.step_index} 步 · ${event.event_type === 'OBSERVATION_CREATED'
                ? '起点' : event.event_type === 'EPISODE_FINISHED' ? '终止结果' : '公开动作'}` : '轨迹暂不可读'}
            </li>;
          })}
        </ul> : null}
        <p className="metric-sub">评审 Token {review.token_usage
          ? `输入 ${review.token_usage.prompt_tokens} / 输出 ${review.token_usage.completion_tokens}` : '未知'}
          {' · '}评审估算费用 {review.estimated_cost?.is_known ? `$${review.estimated_cost.amount} USD` : '未知'}</p>
    </article>;
  }

  return <details className="comparison-judge" onToggle={event => setOpen(event.currentTarget.open)}>
    <summary>双局模型评审</summary>
    <div className="comparison-judge-body">
      <p>第三方模型分析哪一步改变了路线、当时能知道什么，以及这两局能支持什么结论。通关仍以规则判定。</p>
      <div className="review-judge-controls">
        <label>评审模型
          <select className="form-select" value={judge} onChange={event => setJudge(event.target.value)} disabled={pending}>
            <option value="">请选择评审模型</option>
            {candidates.map(model => <option key={model.id} value={model.id}>{model.name}</option>)}
          </select>
        </label>
        <button type="button" className="btn-primary" onClick={() => void submit()}
          disabled={pending || !ready || !artifacts || !hasActions || !candidates.some(model => model.id === judge)}>
          {pending ? '评审中…' : '评审这两局'}
        </button>
      </div>
      <p className="metric-sub">{!hasActions ? '两局均无环境动作。'
        : candidates.length === 0 ? '暂无不同于两局参评模型的可选评审模型。'
          : '点击后发起一次真实模型请求，评审用量单独记录。'}</p>
      {pending ? <div className="comparison-judge-loading" role="status">
        <picture>
          <source media="(prefers-reduced-motion: reduce)" srcSet="/brand/fox-mark.svg" />
          <img src="/brand/fox-loading.svg" width="64" height="64" alt=""
            onError={event => {
              if (event.currentTarget.src.endsWith('fox-loading.svg')) {
                event.currentTarget.src = '/brand/fox-mark.svg';
              }
            }} />
        </picture>
        <p>正在等待评审模型返回。</p>
      </div> : <>
        {loading && <p role="status">正在读取评审记录…</p>}
        {(readFailed || error) && <div role="alert">
          <p>{readFailed ? '评审记录读取失败。' : error}</p>
          <button type="button" className="btn-secondary" onClick={() => {
            setError('');
            setReady(false);
            setRevision(value => value + 1);
          }}>重新读取评审记录</button>
        </div>}
        {skipped > 0 && <p role="status">{skipped} 条评审记录校验失败，已跳过。</p>}
        {current && renderReview(current)}
        {history.length > 0 && <details className="comparison-judge-history">
          <summary>历史评审（{history.length}）</summary>
          {history.map(renderReview)}
        </details>}
      </>}
    </div>
  </details>;
}
