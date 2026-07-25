import classes from "./modules/SlideVisual.module.css";

export type SlideVariant = "overview" | "speed" | "scale";

const TREND = [34, 40, 30, 46, 52, 44, 58, 63, 55, 70, 76, 68, 84, 100];
const LATENCY = [96, 72, 40, 22, 12, 7, 4, 2];

// Mirrors the real analytics modal: a total-clicks hero, orange clicks-by-day
// bars, and a ranked top-referrers list (label + count over a thin bar). The
// null-referrer row reads "Direct / none" in muted italics, just like the app.
function Overview() {
  const referrers = [
    { name: "google.com", clicks: 48210, muted: false },
    { name: "twitter.com", clicks: 31905, muted: false },
    { name: "Direct / none", clicks: 24880, muted: true },
  ];
  const max = Math.max(...referrers.map((r) => r.clicks));

  return (
    <>
      <div className={classes.card}>
        <div className={classes.label}>Total clicks</div>
        <span className={`${classes.value} ${classes.big}`}>128,540</span>

        <div className={classes.subLabel}>Clicks by day</div>
        <div className={classes.bars} aria-hidden>
          {TREND.map((h, i) => (
            <div
              key={i}
              className={`${classes.bar} ${classes.overviewBar}`}
              style={{ height: `${h}%` }}
            />
          ))}
        </div>
      </div>

      <div className={classes.card}>
        <div className={classes.label}>Top referrers</div>
        <div className={classes.ranked}>
          {referrers.map((r) => (
            <div key={r.name}>
              <div className={classes.rankTop}>
                <span
                  className={`${classes.rankName} ${
                    r.muted ? classes.rankNameMuted : ""
                  }`}
                >
                  {r.name}
                </span>
                <span className={classes.rankVal}>
                  {r.clicks.toLocaleString()}
                </span>
              </div>
              <div className={classes.rankTrack}>
                <div
                  className={classes.rankFill}
                  style={{ width: `${(r.clicks / max) * 100}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

function Speed() {
  return (
    <>
      <div className={classes.card}>
        <div className={classes.label}>Redirect latency · p50</div>
        <div className={classes.row}>
          <span className={`${classes.value} ${classes.big}`}>
            4.2<span style={{ fontSize: 16, color: "var(--ink-2)", marginLeft: 4 }}>ms</span>
          </span>
          <span className={classes.sub}>p95 11 ms · p99 23 ms</span>
        </div>
        <div className={classes.bars} aria-hidden>
          {LATENCY.map((h, i) => (
            <div key={i} className={classes.bar} style={{ height: `${h}%` }} />
          ))}
        </div>
      </div>
      <div className={classes.card}>
        <div className={classes.row}>
          <span className={classes.label}>Cache hit rate</span>
          <span className={classes.value} style={{ fontSize: 16 }}>98.3%</span>
        </div>
        <div className={classes.meterTrack}>
          <div className={classes.meterFill} style={{ width: "98.3%" }} />
        </div>
      </div>
    </>
  );
}

function Scale() {
  return (
    <div className={classes.card}>
      <div className={classes.label}>Request flow</div>
      <svg className={classes.diagram} viewBox="0 0 260 236" role="img"
           aria-label="FastAPI with Redis cache and queue, Postgres store, and an arq worker">
        <defs>
          <marker id="arrow" markerWidth="7" markerHeight="7" refX="5.5" refY="3" orient="auto">
            <path d="M0,0 L6,3 L0,6 Z" fill="#4a5060" />
          </marker>
        </defs>
        <path className={classes.edge} d="M130,52 C130,72 70,72 70,96" markerEnd="url(#arrow)" />
        <path className={classes.edge} d="M130,52 C130,72 190,72 190,96" markerEnd="url(#arrow)" />
        <path className={classes.edge} d="M70,138 C70,160 110,160 110,182" markerEnd="url(#arrow)" />
        <rect className={classes.nodeBox} x="80" y="14" width="100" height="38" rx="9" />
        <text className={classes.nodeName} x="130" y="31" textAnchor="middle">FastAPI</text>
        <text className={classes.nodeSub} x="130" y="44" textAnchor="middle">async API</text>
        <rect className={classes.nodeBox} x="22" y="96" width="96" height="42" rx="9" />
        <text className={classes.nodeName} x="70" y="115" textAnchor="middle">Redis</text>
        <text className={classes.nodeSub} x="70" y="128" textAnchor="middle">cache · queue</text>
        <rect className={classes.nodeBox} x="142" y="96" width="96" height="42" rx="9" />
        <text className={classes.nodeName} x="190" y="115" textAnchor="middle">Postgres</text>
        <text className={classes.nodeSub} x="190" y="128" textAnchor="middle">durable store</text>
        <rect className={classes.nodeBox} x="58" y="182" width="104" height="42" rx="9" />
        <text className={classes.nodeName} x="110" y="201" textAnchor="middle">arq worker</text>
        <text className={classes.nodeSub} x="110" y="214" textAnchor="middle">click analytics</text>
      </svg>
    </div>
  );
}

export default function SlideVisual({ variant }: { variant: SlideVariant }) {
  return (
    <div className={classes.root}>
      {variant === "overview" ? <Overview /> : variant === "speed" ? <Speed /> : <Scale />}
    </div>
  );
}