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
  { label: '♠ 黑桃', value: 's', symbol: '♠', color: 'black' as const },
  { label: '♥ 红桃', value: 'h', symbol: '♥', color: 'red' as const },
  { label: '♦ 方片', value: 'd', symbol: '♦', color: 'red' as const },
  { label: '♣ 梅花', value: 'c', symbol: '♣', color: 'black' as const }
];

const RANKS = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2'];

export default function App() {
  const [card1Rank, setCard1Rank] = useState('A');
  const [card1Suit, setCard1Suit] = useState('s');
  const [card2Rank, setCard2Rank] = useState('A');
  const [card2Suit, setCard2Suit] = useState('d');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<EvaluationResponse | null>(null);

  const cardCombo = useMemo(() => `${card1Rank}${card1Suit},${card2Rank}${card2Suit}`, [card1Rank, card1Suit, card2Rank, card2Suit]);
  const players = 6;
  const timeoutMs = 800;
  const mode = 'solver';

  type DeckCard = {
    id: string;
    rank: string;
    suitSymbol: string;
    colorClass: 'red' | 'black';
    left: number;
    delay: number;
    duration: number;
    scale: number;
  };

  const formattedApiUrl = useMemo(() => {
    const url = new URL('/preflop', API_BASE_URL);
    url.searchParams.set('cards', cardCombo);
    url.searchParams.set('players', players.toString());
    if (mode) url.searchParams.set('mode', mode);
    if (timeoutMs) url.searchParams.set('timeoutMs', timeoutMs.toString());
    return url.toString();
  }, [cardCombo, players, mode, timeoutMs]);

  const cardRain = useMemo<DeckCard[]>(() => {
    const deck: DeckCard[] = [];
    SUITS.forEach((suit, suitIndex) => {
      RANKS.forEach((rank, rankIndex) => {
        const left = ((rankIndex * 7 + suitIndex * 13) % 120) - 10;
        const delay = ((rankIndex * 0.5 + suitIndex * 0.8) % 12);
        const duration = 14 + ((rankIndex + suitIndex) % 6) * 2;
        const scale = 0.85 + ((rankIndex % 4) * 0.04);
        deck.push({
          id: `${rank}${suit.value}`,
          rank,
          suitSymbol: suit.symbol,
          colorClass: suit.color,
          left,
          delay,
          duration,
          scale
        });
      });
    });
    return deck;
  }, []);

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
    <div className="page-wrapper">
      <div className="card-rain" aria-hidden="true">
        {cardRain.map((card) => (
          <div
            key={card.id}
            className={`card-floating card-${card.colorClass}`}
            style={{
              left: `${card.left}%`,
              animationDelay: `${card.delay}s`,
              animationDuration: `${card.duration}s`,
              ['--card-scale' as any]: card.scale
            }}
          >
            <div className="card-face">
              <span className="card-rank">{card.rank}</span>
              <span className="card-suit">{card.suitSymbol}</span>
            </div>
          </div>
        ))}
      </div>

      <div className="container">
        <header>
          <h1>
            Born to be the <span className="highlight-king">King</span> of Texas
          </h1>
          <p className="subtitle">I’ll help you keep winning—winning all the way to Mars.</p>
        </header>

        <form onSubmit={handleSubmit}>
          <div className="form-grid">
            <div>
              <label>起手牌</label>
              <div className="card-grid">
                {renderCardSelector('第一张牌', card1Rank, card1Suit, setCard1Rank, setCard1Suit)}
                {renderCardSelector('第二张牌', card2Rank, card2Suit, setCard2Rank, setCard2Suit)}
              </div>
            </div>

          <div>
            <label>求解模式</label>
            <div className="mode-selector">求解器</div>
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
    </div>
  );
}
