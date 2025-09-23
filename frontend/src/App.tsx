import { FormEvent, useMemo, useState } from 'react';

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') || 'https://your-preflop-service.onrender.com';

interface EvaluationResponse {
  cards: string;
  players: number;
  method: string;
  winProbability: number;
  tieProbability: number;
  lossProbability: number;
  expectedValueBb: number;
  percentile: number;
  recommendation: string;
  confidence: number;
  tips: string;
  solverLatencyMs: number;
  iterations: number | null;
  fallback: { reason: string } | null;
  score: number | null;
}

const PRESET_HANDS: Array<{ label: string; value: string }> = [
  { label: 'AA (As,Ad)', value: 'As,Ad' },
  { label: 'KK (Kh,Kc)', value: 'Kh,Kc' },
  { label: 'AKs (As,Ks)', value: 'As,Ks' },
  { label: 'AJs (Ad,Jd)', value: 'Ad,Jd' },
  { label: '76s (7h,6h)', value: '7h,6h' },
  { label: '72o (7h,2c)', value: '7h,2c' }
];

const modes = [
  { value: 'solver', label: 'Solver' },
  { value: 'heuristic', label: 'Heuristic (Chen formula)' }
];

export default function App() {
  const [cards, setCards] = useState('As,Ad');
  const [players, setPlayers] = useState(6);
  const [mode, setMode] = useState('solver');
  const [timeoutMs, setTimeoutMs] = useState(800);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<EvaluationResponse | null>(null);

  const formattedApiUrl = useMemo(() => {
    const url = new URL('/preflop', API_BASE_URL);
    url.searchParams.set('cards', cards);
    url.searchParams.set('players', players.toString());
    if (mode) url.searchParams.set('mode', mode);
    if (timeoutMs) url.searchParams.set('timeoutMs', timeoutMs.toString());
    return url.toString();
  }, [cards, players, mode, timeoutMs]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await fetch(formattedApiUrl);
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail?.error || `Request failed: ${response.status}`);
      }
      const data: EvaluationResponse = await response.json();
      setResult(data);
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Unexpected error');
      }
    } finally {
      setLoading(false);
    }
  };

  const handlePreset = (value: string) => {
    setCards(value);
  };

  const clearResult = () => {
    setResult(null);
    setError(null);
  };

  return (
    <div className="container">
      <header>
        <h1>Texas Preflop Evaluator</h1>
        <p className="description">
          输入你的德州扑克起手牌和桌面玩家数，实时获取基于求解器的胜率、期望收益与策略建议。
        </p>
      </header>

      <form onSubmit={handleSubmit}>
        <div className="form-grid">
          <div>
            <label htmlFor="cards">起手牌 (例如 As,Ad)</label>
            <input
              id="cards"
              name="cards"
              value={cards}
              onChange={(event) => setCards(event.target.value.trim())}
              placeholder="例如 As,Ad"
              required
            />
            <div className="preset-actions" style={{ marginTop: '0.75rem', display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
              {PRESET_HANDS.map((preset) => (
                <button
                  type="button"
                  key={preset.value}
                  className="secondary"
                  style={{ padding: '0.45rem 0.9rem', fontSize: '0.85rem' }}
                  onClick={() => handlePreset(preset.value)}
                >
                  {preset.label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label htmlFor="players">玩家数</label>
            <input
              id="players"
              name="players"
              type="number"
              min={2}
              max={10}
              value={players}
              onChange={(event) => setPlayers(Number(event.target.value))}
            />
          </div>

          <div>
            <label htmlFor="mode">求解模式</label>
            <select id="mode" value={mode} onChange={(event) => setMode(event.target.value)}>
              {modes.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="timeout">求解器超时 (ms)</label>
            <input
              id="timeout"
              name="timeout"
              type="number"
              min={200}
              max={5000}
              step={100}
              value={timeoutMs}
              onChange={(event) => setTimeoutMs(Number(event.target.value))}
            />
          </div>
        </div>

        <div className="actions">
          <button type="submit" className="primary" disabled={loading}>
            {loading ? '计算中…' : '计算策略'}
          </button>
          <button type="button" className="secondary" onClick={clearResult}>
            清除结果
          </button>
        </div>

        <div className="status">API 入口：{API_BASE_URL}</div>
      </form>

      {error && <div className="alert">{error}</div>}

      {result && (
        <section className="result-card">
          <h2>评估结果</h2>
          <div className="result-grid">
            <div className="result-entry">
              <h3>推荐策略</h3>
              <p>{result.recommendation.toUpperCase()}</p>
            </div>
            <div className="result-entry">
              <h3>胜率</h3>
              <p>{(result.winProbability * 100).toFixed(2)}%</p>
            </div>
            <div className="result-entry">
              <h3>期望收益 (EV)</h3>
              <p>{result.expectedValueBb.toFixed(2)} bb</p>
            </div>
            <div className="result-entry">
              <h3>置信度</h3>
              <p>{(result.confidence * 100).toFixed(1)}%</p>
            </div>
            <div className="result-entry">
              <h3>使用方法</h3>
              <p>{result.method}</p>
            </div>
            <div className="result-entry">
              <h3>求解耗时</h3>
              <p>{result.solverLatencyMs} ms</p>
            </div>
          </div>

          <div className="disclaimer">
            <strong>提示：</strong> {result.tips}
            {result.fallback && (
              <div style={{ marginTop: '0.75rem', color: '#b91c1c' }}>
                当前结果来自 fallback ({result.fallback.reason})，请检查求解器状态。
              </div>
            )}
          </div>
        </section>
      )}
    </div>
  );
}
