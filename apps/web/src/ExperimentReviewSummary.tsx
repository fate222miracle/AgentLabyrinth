import { useEffect, useMemo, useState } from 'react';

import { readApi } from './apiClient';
import {
  episodeReviewListResponseSchema,
  requireIdentity,
  type EpisodeReview,
  type ExperimentArtifact,
} from './apiContracts';

interface Props { experiment: ExperimentArtifact }

/** Load review coverage only when opened; read operations never invoke a Judge. */
export function ExperimentReviewSummary({ experiment }: Props) {
  const [opened, setOpened] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [reviews, setReviews] = useState<EpisodeReview[]>([]);
  const [reviewedEpisodes, setReviewedEpisodes] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    setOpened(false);
    setLoaded(false);
    setReviews([]);
    setReviewedEpisodes(0);
    setError('');
  }, [experiment.experiment_id]);

  useEffect(() => {
    if (!opened || loaded) return;
    const controller = new AbortController();
    setLoading(true);
    void Promise.all(experiment.episode_ids.map(async (episodeId) => {
      const response = await fetch(`/api/v1/episodes/${encodeURIComponent(episodeId)}/reviews`, {
        signal: controller.signal,
      });
      const data = await readApi(response, episodeReviewListResponseSchema);
      requireIdentity(data.episode_id, episodeId);
      return data.reviews;
    })).then((groups) => {
      setReviewedEpisodes(groups.filter((group) => group.some((review) =>
        review.method === 'llm_judge' && review.provider !== 'fake')).length);
      setReviews(groups.flat());
      setLoaded(true);
    }).catch((reason: unknown) => {
      if (!controller.signal.aborted) {
        setError(reason instanceof Error ? reason.message : '复核覆盖读取失败。');
        setLoaded(true);
      }
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false);
    });
    return () => controller.abort();
  }, [experiment.episode_ids, loaded, opened]);

  const summary = useMemo(() => {
    const expected = new Map<string, boolean>();
    for (const pair of experiment.pairs) {
      expected.set(pair.baseline_episode_id, pair.baseline_success);
      expected.set(pair.recovery_episode_id, pair.recovery_success);
    }
    const actual = reviews.filter((review) => review.method === 'llm_judge' && review.provider !== 'fake');
    const completed = actual.filter((review) => review.status === 'completed');
    const comparable = completed.filter((review) => review.verdict !== 'uncertain');
    const agreements = comparable.filter((review) =>
      (review.verdict === 'pass') === expected.get(review.episode_id)).length;
    return {
      completed: completed.length,
      failed: actual.length - completed.length,
      passed: completed.filter((review) => review.verdict === 'pass').length,
      rejected: completed.filter((review) => review.verdict === 'fail').length,
      uncertain: completed.filter((review) => review.verdict === 'uncertain').length,
      comparable: comparable.length,
      agreements,
    };
  }, [experiment.pairs, reviews]);

  return (
    <details className="experiment-review-summary"
      onToggle={(event) => setOpened(event.currentTarget.open)}>
      <summary>已保存的模型评审 <span>只读查看，不重新调用模型</span></summary>
      <div className="review-summary-grid" aria-live="polite">
        <div><strong>{reviewedEpisodes} / {experiment.episode_ids.length}</strong><span>已有复核的运行</span></div>
        <div><strong>{summary.completed}</strong><span>已完成的复核</span></div>
        <div><strong>{summary.passed} / {summary.rejected} / {summary.uncertain}</strong><span>通过 / 不通过 / 暂无法判断</span></div>
        <div><strong>{summary.comparable ? `${summary.agreements} / ${summary.comparable}` : '暂无'}</strong><span>与规则评分同向</span></div>
      </div>
      {loading && <p role="status" className="loading-note">正在读取各 Episode 的独立复核…</p>}
      {error && <p role="alert" className="review-failure">{error}</p>}
      {!loading && !error && reviewedEpisodes === 0 && <p className="metric-sub">当前实验没有已保存的大模型评审。</p>}
      {summary.failed > 0 && <p className="metric-sub">另有 {summary.failed} 条复核链路失败记录，未计入结论统计。</p>}
    </details>
  );
}
