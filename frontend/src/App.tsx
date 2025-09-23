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

const SUITS = [
  { label: '♠️ 黑桃 (s)', value: 's' },
  { label: '♥️ 红桃 (h)', value: 'h' },
  { label: '♦️ 方片 (d)', value: 'd' },
  { label: '♣️ 梅花 (c)', value: 'c' }
];

const RANKS = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2'];

const PRESET_HANDS: Array<{ label: string; cards: [string, string] }> = [
  { label: 'AA (As,Ad)', cards: ['As', 'Ad'] },
  { label: 'KK (Kh,Kc)', cards: ['Kh', 'Kc'] },
  { label: 'AKs (As,Ks)', cards: ['As', 'Ks'] },
  { label: 'AJs (Ad,Jd)', cards: ['Ad', 'Jd'] },
  { label: '76s (7h,6h)', cards: ['7h', '6h'] },
  { label: '72o (7h,2c)', cards: ['7h', '2c'] }
];

const modes = [
  { value: 'solver', label: 'Solver' },
  { value: 'heuristic', label: 'Heuristic (Chen formula)' }
];

export default function App() {
  const [card1Rank, setCard1Rank] = useState('A');
  const [card1Suit, setCard1Suit] = useState('s');
  const [card2Rank, setCard2Rank] = useState('A');
  const [card2Suit, setCard2Suit] = useState('d');
  const [mode, setMode] = useState('solver');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<EvaluationResponse | null>(null);

  const cardCombo = useMemo(() => `${card1Rank}${card1Suit},${card2Rank}${card2Suit}`, [card1Rank, card1Suit, card2Rank, card2Suit]);
  const players = 6;
  const timeoutMs = 800;

  const formattedApiUrl = useMemo(() => {
    const url = new URL('/preflop', API_BASE_URL);
    url.searchParams.set('cards', cardCombo);
    url.searchParams.set('players', players.toString());
    if (mode) url.searchParams.set('mode', mode);
    if (timeoutMs) url.searchParams.set('timeoutMs', timeoutMs.toString());
    return url.toString();
  }, [cardCombo, players, mode, timeoutMs]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (card1Rank === card2Rank && card1Suit === card2Suit) {
      setError('两张牌不能完全相同，请重新选择。');
      setResult(null);
      return;
    }
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

  const handlePreset = (cards: [string, string]) => {
    const [first, second] = cards;
    setCard1Rank(first[0]);
    setCard1Suit(first[1]);
    setCard2Rank(second[0]);
    setCard2Suit(second[1]);
  };

  const clearResult = () => {
    setResult(null);
    setError(null);
  };

  const renderCardSelector = (label: string, rank: string, suit: string, setRank: (value: string) => void, setSuit: (value: string) => void) => (
    <div className="card-selector">
      <label>{label}</label>
      <div className="card-inputs">
        <select value={rank} onChange={(event) => setRank(event.target.value)}>
          {RANKS.map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>
        <select value={suit} onChange={(event) => setSuit(event.target.value)}>
          {SUITS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>
    </div>
  );

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
            <label>起手牌</label>
            <div className="card-grid">
              {renderCardSelector('第一张牌', card1Rank, card1Suit, setCard1Rank, setCard1Suit)}
              {renderCardSelector('第二张牌', card2Rank, card2Suit, setCard2Rank, setCard2Suit)}
            </div>
            <div className="preset-actions" style={{ marginTop: '0.75rem', display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
              {PRESET_HANDS.map((preset) => (
                <button
                  type="button"
                  key={preset.label}
                  className="secondary"
                  style={{ padding: '0.45rem 0.9rem', fontSize: '0.85rem' }}
                  onClick={() => handlePreset(preset.cards)}
                >
                  {preset.label}
                </button>
              ))}
            </div>
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
