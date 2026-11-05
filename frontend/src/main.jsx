import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { CssBaseline, ThemeProvider, createTheme } from "@mui/material";
import "./styles.css";
import "./timeframe.css";
import "./admin.css";
import "./notifications.css";
import "./design.css";

const API_BASE = (import.meta.env.VITE_API_URL || "/api").replace(/\/$/, "");

const theme = createTheme({
  palette: {
    mode: "dark",
    primary: { main: "#18c7b5", contrastText: "#061312" },
    secondary: { main: "#65e3d1" },
    background: { default: "#081012", paper: "#101a1d" },
    text: { primary: "#edf7f5", secondary: "#9bb0ae" },
    divider: "#2a3b3e",
  },
  shape: { borderRadius: 12 },
  typography: { fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif", button: { textTransform: "none", fontWeight: 700 } },
  components: {
    MuiButton: { defaultProps: { variant: "contained" }, styleOverrides: { root: { minHeight: 44, borderRadius: 10, boxShadow: "none" } } },
    MuiTextField: { defaultProps: { variant: "outlined", size: "medium" } },
    MuiDialog: { styleOverrides: { paper: { backgroundImage: "none", border: "1px solid #2a3b3e" } } },
  },
});

const request = async (path, options = {}) => {
  const token = localStorage.getItem("heartstake_token");
  const endpoint = `${API_BASE}${path}`;
  const response = await fetch(endpoint, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Token ${token}` } : {}),
      ...options.headers,
    },
  });
  const contentType = response.headers.get("content-type") || "";
  const raw = await response.text();
  let data;

  if (contentType.includes("application/json")) {
    try {
      data = raw ? JSON.parse(raw) : {};
    } catch {
      throw new Error(
        `invalid JSON from ${endpoint} (HTTP ${response.status})`,
      );
    }
  } else {
    const detail =
      raw.trim().startsWith("<!DOCTYPE") || raw.trim().startsWith("<html")
        ? "server returned an HTML page"
        : raw.trim().slice(0, 100);
    throw new Error(
      `${detail || "empty response"} from ${endpoint} (HTTP ${response.status})`,
    );
  }

  if (!response.ok)
    throw new Error(data.error || `request failed (HTTP ${response.status})`);
  return data;
};

const fmt = (value) =>
  Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 });
const dateLabel = (value) =>
  value
    ? new Date(value).toLocaleDateString(undefined, {
        day: "numeric",
        month: "short",
        year: "numeric",
      })
    : "—";
const quarterKey = (value) => {
  if (!value) return "";
  const date = new Date(value);
  return `${date.getFullYear()}-${Math.floor(date.getMonth() / 3)}`;
};
const quarterEnd = (value) => {
  if (!value) return null;
  const date = new Date(value);
  return new Date(
    date.getFullYear(),
    Math.floor(date.getMonth() / 3) * 3 + 3,
    0,
  );
};
const quarterTradingEnd = (value) => {
  if (!value) return null;
  const date = new Date(value);
  return new Date(
    date.getFullYear(),
    Math.floor(date.getMonth() / 3) * 3 + 2,
    0,
  );
};

function AccessForm({ onAuthenticated }) {
  const [mode, setMode] = useState("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await request(`/auth/${mode}/`, {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      localStorage.setItem("heartstake_token", result.token);
      onAuthenticated(result.user);
    } catch (caught) {
      setError(caught.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="access-page">
      <section className="access-panel">
        <header className="panel-header">
          <span>
            <b>♥</b> HEARTSTAKE_OS
          </span>
          <span className="status">
            <i /> NETWORK ONLINE
          </span>
        </header>
        <div className="panel-body">
          <p className="path">root@heartstake:~/access$</p>
          <h1>{mode === "login" ? "AUTHENTICATE_" : "CREATE_IDENTITY_"}</h1>
          <p className="intro">
            {mode === "login"
              ? "Enter credentials to access prediction markets."
              : "Create a local identity. No email required."}
          </p>
          <div className="tabs" role="tablist" aria-label="Account access">
            <button
              type="button"
              role="tab"
              aria-selected={mode === "login"}
              className={mode === "login" ? "active" : ""}
              onClick={() => {
                setMode("login");
                setError("");
              }}
            >
              Log in
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={mode === "register"}
              className={mode === "register" ? "active" : ""}
              onClick={() => {
                setMode("register");
                setError("");
              }}
            >
              Register
            </button>
          </div>
          <form onSubmit={submit}>
            <label>
              <span>HANDLE</span>
              <input
                autoFocus
                autoComplete="username"
                minLength="3"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="user_id"
                required
              />
            </label>
            <label>
              <span>PASSKEY</span>
              <input
                type="password"
                autoComplete={
                  mode === "login" ? "current-password" : "new-password"
                }
                minLength="8"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="passkey"
                required
              />
            </label>
            {error && (
              <p className="form-error" role="alert">
                {error}
              </p>
            )}
            <button className="submit" disabled={busy}>
              {busy
                ? "PROCESSING..."
                : mode === "login"
                  ? "ENTER SYSTEM  →"
                  : "INITIALIZE ACCOUNT  →"}
            </button>
          </form>
        </div>
        <footer className="panel-footer">
          BUILD 0.2.0 <span>PLAY_CREDITS_ONLY</span>
        </footer>
      </section>
    </main>
  );
}

function BetDialog({ market, outcome, balance, onClose, onComplete }) {
  const [amount, setAmount] = useState("25");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const estimate = Number(outcome.pool)
    ? ((Number(market.pool) + Number(amount || 0)) /
        (Number(outcome.pool) + Number(amount || 0))) *
      Number(amount || 0)
    : Number(amount || 0);
  useEffect(() => {
    const closeOnEscape = (event) => event.key === "Escape" && onClose();
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [onClose]);

  const place = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await request("/bets/", {
        method: "POST",
        body: JSON.stringify({ outcome_id: outcome.id, amount }),
      });
      onComplete(result.balance);
      onClose();
    } catch (caught) {
      setError(caught.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="overlay"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <section
        className="bet-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="bet-dialog-title"
      >
        <header>
          <span>Place a bet</span>
          <button type="button" aria-label="Close bet dialog" onClick={onClose}>
            ×
          </button>
        </header>
        <div className="dialog-body">
          <p className="code">
            MARKET_{String(market.id).padStart(3, "0")} / OUTCOME_{outcome.id}
          </p>
          <h2 id="bet-dialog-title">{outcome.label}</h2>
          <p>{market.title}</p>
          {market.mode === "TIMEFRAME" && (
            <p className="market-dates">
              Trading closes {dateLabel(market.closes_at)} · resolves{" "}
              {dateLabel(market.resolves_at)}
            </p>
          )}
          <form onSubmit={place}>
            <label>
              <span>STAKE_AMOUNT</span>
              <div className="credit-input">
                <input
                  type="number"
                  min="1"
                  max={balance}
                  step="1"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  required
                />
                <b>CR</b>
              </div>
            </label>
            <div className="quick">
              {[10, 25, 50, 100].map((value) => (
                <button
                  type="button"
                  key={value}
                  onClick={() => setAmount(String(Math.min(value, balance)))}
                >
                  +{value}
                </button>
              ))}
            </div>
            <dl>
              <div>
                <dt>CURRENT PROBABILITY</dt>
                <dd>
                  {outcome.probability == null
                    ? "—"
                    : `${outcome.probability}%`}
                </dd>
              </div>
              <div>
                <dt>EST. RETURN</dt>
                <dd className="cyan">{fmt(estimate)} CR</dd>
              </div>
              <div>
                <dt>AVAILABLE</dt>
                <dd>{fmt(balance)} CR</dd>
              </div>
            </dl>
            {error && (
              <p className="form-error" role="alert">
                {error}
              </p>
            )}
            <button className="submit" disabled={busy}>
              {busy ? "TRANSMITTING..." : "CONFIRM POSITION  →"}
            </button>
          </form>
        </div>
      </section>
    </div>
  );
}

function CategoryBoard({ title, subtitle, markets, mode, onSelect }) {
  const [openId, setOpenId] = useState(null);
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const pageSize = 6;
  const active = markets.filter((market) => market.status === "OPEN");
  useEffect(() => {
    setPage(1);
    setOpenId(null);
  }, [query]);

  const controls = (total, pages) => (
    <div className="list-tools">
      <label>
        <span>SEARCH</span>
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="filter_options..."
        />
      </label>
      <span className="result-count">
        {total} RESULT{total === 1 ? "" : "S"}
      </span>
      {pages > 1 && (
        <nav className="pagination" aria-label={`${title} pagination`}>
          <button
            type="button"
            disabled={page === 1}
            onClick={() => setPage((value) => value - 1)}
          >
            Previous
          </button>
          <span>
            Page {page} of {pages}
          </span>
          <button
            type="button"
            disabled={page === pages}
            onClick={() => setPage((value) => value + 1)}
          >
            Next
          </button>
        </nav>
      )}
    </div>
  );

  if (mode === "NEXT_EVENT") {
    const eventMarkets = active;
    const filtered = eventMarkets.flatMap((market) =>
      market.outcomes
        .filter((outcome) =>
          outcome.label.toLowerCase().includes(query.toLowerCase()),
        )
        .map((outcome) => ({ market, outcome })),
    );
    const pages = Math.max(1, Math.ceil(filtered.length / pageSize));
    const visible = filtered.slice((page - 1) * pageSize, page * pageSize);
    return (
      <section className="category-board">
        <header>
          <div>
            <span>NEXT EVENT</span>
            <h2>{title}</h2>
            <p>{subtitle}</p>
          </div>
          <b>{filtered.length} OPTIONS</b>
        </header>
        {eventMarkets.length > 0 && controls(filtered.length, pages)}
        {!eventMarkets.length ? (
          <p className="empty-category">NO ACTIVE MARKET</p>
        ) : !visible.length ? (
          <p className="empty-category">NO MATCHING OPTIONS</p>
        ) : (
          <div className="category-options">
            {visible.map(({ market, outcome }) => (
              <button
                key={`${market.id}-${outcome.id}`}
                onClick={() => onSelect(market, outcome)}
              >
                <span>
                  <strong>{outcome.label}</strong>
                  <small>{fmt(outcome.pool)} CR POOL</small>
                </span>
                <span className="option-price">
                  {outcome.probability == null
                    ? "—"
                    : `${outcome.probability}%`}
                </span>
                <em>BET →</em>
              </button>
            ))}
          </div>
        )}
      </section>
    );
  }

  // A category may contain several markets, but they must all belong to the
  // same currently available quarterly timeframe.
  const timeframeMonth = [...active].sort(
    (first, second) => new Date(first.closes_at) - new Date(second.closes_at),
  )[0];
  const currentTimeframe = timeframeMonth
    ? active.filter(
        (market) =>
          quarterKey(market.closes_at) === quarterKey(timeframeMonth.closes_at),
      )
    : [];
  const filtered = currentTimeframe.filter((market) =>
    market.title.toLowerCase().includes(query.toLowerCase()),
  );
  const pages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const visible = filtered.slice((page - 1) * pageSize, page * pageSize);

  return (
    <section className="category-board timeframe-board">
      <header>
        <div>
          <span>QUARTERLY TRADING · QUARTER-END RESOLUTION</span>
          <h2>{title}</h2>
          <p>{subtitle}</p>
        </div>
        <b>{currentTimeframe.length} OPTIONS</b>
      </header>
      {controls(filtered.length, pages)}
      {!visible.length ? (
        <p className="empty-category">NO MATCHING OPTIONS</p>
      ) : (
        <div className="timeframe-options">
          {visible.map((market) => {
            const expanded = openId === market.id;
            const optionName = market.title
              .replace(/^Current:\s*/i, "")
              .replace(/ within (90 days|this quarter)$/i, "");
            return (
              <div
                className={`timeframe-item ${expanded ? "expanded" : ""}`}
                key={market.id}
              >
                <button
                  className="timeframe-summary"
                  type="button"
                  aria-expanded={expanded}
                  onClick={() => setOpenId(expanded ? null : market.id)}
                >
                  <span>
                    <strong>{optionName}</strong>
                    <small>
                      Trade until{" "}
                      {dateLabel(quarterTradingEnd(market.closes_at))} · resolve{" "}
                      {dateLabel(quarterEnd(market.resolves_at))} ·{" "}
                      {fmt(market.pool)} credits
                    </small>
                  </span>
                  <em>{expanded ? "Hide" : "View options"}</em>
                </button>
                {expanded && (
                  <div className="binary-options">
                    {market.outcomes.map((outcome) => (
                      <button
                        className={outcome.label === "FOR" ? "for" : "against"}
                        key={outcome.id}
                        onClick={() => onSelect(market, outcome)}
                      >
                        <span>{outcome.label}</span>
                        <strong>
                          {outcome.probability == null
                            ? "—"
                            : `${outcome.probability}%`}
                        </strong>
                        <small>{fmt(outcome.pool)} CR</small>
                        <em>BET {outcome.label} →</em>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}

function AdminPanel({ onBack, user }) {
  const [data, setData] = useState({
    people: [],
    relationships: [],
    users: [],
  });
  const [name, setName] = useState("");
  const [pair, setPair] = useState({ person_a_id: "", person_b_id: "" });
  const [message, setMessage] = useState("");
  const [dialog, setDialog] = useState(null);
  const load = () =>
    Promise.all([request("/admin/people/"), request("/admin/users/")])
      .then(([roster, accounts]) =>
        setData({ ...roster, users: accounts.users }),
      )
      .catch((error) => setMessage(error.message));
  useEffect(() => {
    load();
  }, []);

  const act = async (operation) => {
    setMessage("");
    try {
      await operation();
      await load();
    } catch (error) {
      setMessage(error.message);
    }
  };
  const addPerson = (event) => {
    event.preventDefault();
    act(() =>
      request("/admin/people/", {
        method: "POST",
        body: JSON.stringify({ name }),
      }).then(() => setName("")),
    );
  };
  const addRelationship = (event) => {
    event.preventDefault();
    act(() =>
      request("/admin/relationships/", {
        method: "POST",
        body: JSON.stringify(pair),
      }).then(() => setPair({ person_a_id: "", person_b_id: "" })),
    );
  };
  const updateUser = (account, changes) =>
    act(() =>
      request(`/admin/users/${account.id}/`, {
        method: "POST",
        body: JSON.stringify(changes),
      }),
    );
  const ask = (title, message, action, confirmLabel = "Confirm") =>
    setDialog({ title, message, action, confirmLabel });
  const removeUser = (account) =>
    ask("Remove user", `Remove ${account.username}? This permanently deletes the account and its bets.`, () =>
      act(() => request(`/admin/users/${account.id}/`, { method: "DELETE" })), "Remove");

  return (
    <main className="dashboard admin-view">
      <button className="back-button" type="button" onClick={onBack}>
        ← Return to markets
      </button>
      <div className="dashboard-head">
        <div>
          <p className="path">root@heartstake:~/admin$ roster</p>
          <h1>ADMINISTRATION</h1>
          <p>Manage the active roster and relationship state.</p>
        </div>
        <div className="stat">
          <span>ACTIVE PEOPLE</span>
          <b>{String(data.people.length).padStart(2, "0")}</b>
        </div>
      </div>
      {message && <p className="form-error">! {message}</p>}
      <section className="admin-grid">
        <article className="admin-card">
          <header>
            <span>01</span>
            <h2>USERS</h2>
          </header>
          <div className="admin-list users">
            {data.users.map((account) => (
              <div key={account.id}>
                <span>
                  <b>{account.username}</b>
                  <small>
                    {account.is_admin
                      ? "ADMIN"
                      : account.is_active
                        ? "USER"
                        : "BLOCKED"}{" "}
                    · {account.balance} CR
                  </small>
                </span>
                <select
                  aria-label={`Person linked to ${account.username}`}
                  value={account.person_id || ""}
                  onChange={(event) =>
                    updateUser(account, {
                      person_id: event.target.value || null,
                    })
                  }
                >
                  <option value="">No person linked</option>
                  {data.people.map((person) => (
                    <option key={person.id} value={person.id}>
                      {person.name}
                    </option>
                  ))}
                </select>
                <button
                  onClick={() => {
                    ask("Set credits", `Choose a new credit balance for ${account.username}.`, (value) =>
                      updateUser(account, { balance: value }), "Save credits");
                  }}
                >
                  Set credits
                </button>
                <button
                  disabled={account.id === user?.id}
                  onClick={() =>
                    updateUser(account, { is_active: !account.is_active })
                  }
                >
                  {account.is_active ? "Block" : "Unblock"}
                </button>
                {account.is_active && (
                  <button
                    disabled={account.id === user?.id}
                    onClick={() =>
                      updateUser(account, { is_admin: !account.is_admin })
                    }
                  >
                    {account.is_admin ? "Remove admin" : "Promote admin"}
                  </button>
                )}
                <button
                  className="danger-button"
                  disabled={account.id === user?.id}
                  onClick={() => removeUser(account)}
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
        </article>
        <article className="admin-card">
          <header>
            <span>02</span>
            <h2>PEOPLE</h2>
          </header>
          <form className="inline-form" onSubmit={addPerson}>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="new_person_name"
              required
            />
            <button className="submit">ADD PERSON</button>
          </form>
          <div className="admin-list">
            {data.people.map((person) => (
              <div key={person.id}>
                <span
                  className="admin-avatar"
                  style={{ borderColor: person.color }}
                >
                  {person.initials}
                </span>
                <b>{person.name}</b>
                <button
                  onClick={() =>
                    ask("Remove person", `Remove ${person.name}? This also ends their active relationship.`, () =>
                      act(() => request(`/admin/people/${person.id}/`, { method: "DELETE" })), "Remove")
                  }
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
        </article>
        <article className="admin-card">
          <header>
            <span>03</span>
            <h2>RELATIONSHIPS</h2>
          </header>
          <form className="relationship-form" onSubmit={addRelationship}>
            <select
              value={pair.person_a_id}
              onChange={(e) =>
                setPair({ ...pair, person_a_id: e.target.value })
              }
              required
            >
              <option value="">PERSON A</option>
              {data.people.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
            <span>+</span>
            <select
              value={pair.person_b_id}
              onChange={(e) =>
                setPair({ ...pair, person_b_id: e.target.value })
              }
              required
            >
              <option value="">PERSON B</option>
              {data.people.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
            <button className="submit">DECLARE</button>
          </form>
          <div className="admin-list relationships">
            {data.relationships.map((rel) => (
              <div key={rel.id}>
                <b>{rel.person_a.name}</b>
                <span className="heart-link">♥</span>
                <b>{rel.person_b.name}</b>
                <button
                  onClick={() =>
                    ask("Declare breakup", `Declare the breakup of ${rel.person_a.name} and ${rel.person_b.name}?`, () =>
                      act(() => request(`/admin/relationships/${rel.id}/breakup/`, { method: "POST" })), "Declare breakup")
                  }
                >
                  Declare breakup
                </button>
              </div>
            ))}
            {!data.relationships.length && <p>No active relationships.</p>}
          </div>
        </article>
      </section>
      {dialog && <div className="overlay" onMouseDown={(event) => event.target === event.currentTarget && setDialog(null)}><section className="confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="confirm-dialog-title"><header><span>{dialog.title}</span><button type="button" aria-label="Close dialog" onClick={() => setDialog(null)}>×</button></header><div className="dialog-body"><p id="confirm-dialog-title">{dialog.message}</p>{dialog.title === "Set credits" && <input autoFocus type="number" min="0" step="0.01" defaultValue={data.users.find(account => account.username === dialog.message.split(" for ")[1]?.replace(".", ""))?.balance || "0"} id="credit-value" />}</div><footer className="confirm-actions"><button type="button" onClick={() => setDialog(null)}>Cancel</button><button className="submit" type="button" onClick={() => { const value = document.getElementById("credit-value")?.value; dialog.action(value); setDialog(null); }}>{dialog.confirmLabel}</button></footer></section></div>}
    </main>
  );
}

function Dashboard({ user, setUser, onLogout }) {
  const [markets, setMarkets] = useState([]);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [adminOpen, setAdminOpen] = useState(false);
  const [notifications, setNotifications] = useState(user.notifications || []);

  useEffect(() => {
    const pollNotifications = () =>
      request("/me/")
        .then((result) => {
          setUser(result.user);
          if (result.notifications?.length)
            setNotifications(result.notifications);
        })
        .catch(() => {});
    const interval = window.setInterval(pollNotifications, 10000);
    return () => window.clearInterval(interval);
  }, [setUser]);

  const load = () => {
    setLoading(true);
    setError("");
    return request("/markets/")
      .then((data) => setMarkets(data.markets))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };
  useEffect(() => {
    load();
  }, []);

  const showMarkets = () => {
    setSelected(null);
    setAdminOpen(false);
    load();
  };

  const completed = (balance) => {
    setUser({ ...user, balance });
    load();
  };
  const nextTitles = {
    NEXT: "Current: next person to enter a relationship",
    COUPLE: "Current: next couple to enter a relationship",
    BREAKUP: "Current: next couple to break up",
  };
  const group = (kind, mode) =>
    markets.filter((market) => {
      if (market.kind !== kind || market.mode !== mode) return false;
      if (mode === "NEXT_EVENT") return market.title === nextTitles[kind];
      return (
        market.title.startsWith("Current:") &&
        market.title.toLowerCase().includes("within this quarter") &&
        market.outcomes.some((outcome) => outcome.label === "FOR") &&
        market.outcomes.some((outcome) => outcome.label === "AGAINST")
      );
    });
  const displayedMarketCount = ["NEXT", "COUPLE", "BREAKUP"].reduce(
    (total, kind) =>
      total +
      group(kind, "NEXT_EVENT").length +
      group(kind, "TIMEFRAME").length,
    0,
  );

  return (
    <div className="app-shell">
      {notifications.length > 0 && (
        <aside className="notification-popups" aria-live="polite">
          {notifications.map((notification) => (
            <div className="notification-popup" key={notification.id}>
              <b>BET RESOLVED</b>
              <span>{notification.message}</span>
              <button
                type="button"
                onClick={() =>
                  setNotifications((current) =>
                    current.filter((item) => item.id !== notification.id),
                  )
                }
              >
                ×
              </button>
            </div>
          ))}
        </aside>
      )}
      <header className="topbar">
        <button
          className="wordmark"
          type="button"
          onClick={showMarkets}
          aria-label="Go to markets"
        >
          <b>♥</b> Heartstake<span>Prediction markets</span>
        </button>
        <div className="user-tools">
          <span className="balance">
            {fmt(user.balance)} <small>credits</small>
          </span>
          <span className="username">{user.username}</span>
          {user.is_admin && (
            <button
              type="button"
              className={adminOpen ? "active" : ""}
              onClick={() => (adminOpen ? showMarkets() : setAdminOpen(true))}
            >
              Admin
            </button>
          )}
          <button type="button" onClick={onLogout}>
            Log out
          </button>
        </div>
      </header>
      <aside>
        <nav aria-label="Main navigation">
          <button
            className={!adminOpen ? "active" : ""}
            type="button"
            onClick={showMarkets}
          >
            <span>◫</span> Markets
          </button>
          {user.is_admin && (
            <button
              className={adminOpen ? "active" : ""}
              type="button"
              onClick={() => setAdminOpen(true)}
            >
              <span>⚙</span> Administration
            </button>
          )}
        </nav>
        <p>
          Play credits only.
          <br />
          No real-money value.
        </p>
      </aside>
      {adminOpen ? (
        <AdminPanel user={user} onBack={showMarkets} />
      ) : (
        <main key="markets-view" className="dashboard">
          <div className="dashboard-head">
            <div>
              <p className="path">
                root@heartstake:~/markets$ list --status=open
              </p>
              <h1>ACTIVE MARKETS</h1>
              <p>Choose an outcome and allocate play credits.</p>
            </div>
            <div className="stat">
              <span>OPEN MARKETS</span>
              <b>{displayedMarketCount.toString().padStart(2, "0")}</b>
            </div>
          </div>
          <div className="ticker">
            <span>LIVE DATA FEED</span>
            <div>
              PARIMUTUEL ENGINE ONLINE · PRICES DERIVED FROM ACTIVE POOLS ·
              WINNERS SPLIT TOTAL LIQUIDITY
            </div>
          </div>
          {loading && (
            <p className="terminal-message">LOADING MARKET DATA...</p>
          )}
          {error && <p className="form-error">! {error}</p>}
          <div className="board-section">
            <div className="board-label">
              <span>01</span>
              <div>
                <b>NEXT EVENT</b>
                <small>One winner from the complete option list</small>
              </div>
            </div>
            <div className="category-grid">
              <CategoryBoard
                title="Next person to enter a relationship"
                subtitle="Choose from every available person."
                markets={group("NEXT", "NEXT_EVENT")}
                mode="NEXT_EVENT"
                onSelect={(market, outcome) => setSelected({ market, outcome })}
              />
              <CategoryBoard
                title="Next couple to enter a relationship"
                subtitle="Choose from every valid pairing."
                markets={group("COUPLE", "NEXT_EVENT")}
                mode="NEXT_EVENT"
                onSelect={(market, outcome) => setSelected({ market, outcome })}
              />
              <CategoryBoard
                title="Next couple to break up"
                subtitle="Choose from every existing couple."
                markets={group("BREAKUP", "NEXT_EVENT")}
                mode="NEXT_EVENT"
                onSelect={(market, outcome) => setSelected({ market, outcome })}
              />
            </div>
          </div>
          <div className="board-section">
            <div className="board-label">
              <span>02</span>
              <div>
                <b>WITHIN 90 DAYS</b>
                <small>Open any option and bet for or against it</small>
              </div>
            </div>
            <div className="category-grid">
              <CategoryBoard
                title="Person enters a relationship"
                subtitle="Every person is an independent FOR / AGAINST market."
                markets={group("NEXT", "TIMEFRAME")}
                mode="TIMEFRAME"
                onSelect={(market, outcome) => setSelected({ market, outcome })}
              />
              <CategoryBoard
                title="Couple enters a relationship"
                subtitle="Every valid pairing has its own market."
                markets={group("COUPLE", "TIMEFRAME")}
                mode="TIMEFRAME"
                onSelect={(market, outcome) => setSelected({ market, outcome })}
              />
              <CategoryBoard
                title="Couple breaks up"
                subtitle="Every existing couple has its own market."
                markets={group("BREAKUP", "TIMEFRAME")}
                mode="TIMEFRAME"
                onSelect={(market, outcome) => setSelected({ market, outcome })}
              />
            </div>
          </div>
        </main>
      )}
      <footer className="app-footer">
        <span>HEARTSTAKE_OS © 2026</span>
        <span>NO REAL CURRENCY / NO FINANCIAL VALUE</span>
      </footer>
      {selected && (
        <BetDialog
          {...selected}
          balance={Number(user.balance)}
          onClose={() => setSelected(null)}
          onComplete={completed}
        />
      )}
    </div>
  );
}

function App() {
  const [user, setUser] = useState(null);
  const [checking, setChecking] = useState(
    Boolean(localStorage.getItem("heartstake_token")),
  );
  useEffect(() => {
    if (!localStorage.getItem("heartstake_token")) return;
    request("/me/")
      .then((r) => setUser({ ...r.user, notifications: r.notifications || [] }))
      .catch(() => localStorage.removeItem("heartstake_token"))
      .finally(() => setChecking(false));
  }, []);
  const logout = async () => {
    try {
      await request("/auth/logout/", { method: "POST" });
    } finally {
      localStorage.removeItem("heartstake_token");
      setUser(null);
    }
  };
  if (checking)
    return <main className="loading-page">ESTABLISHING SECURE SESSION...</main>;
  return user ? (
    <Dashboard user={user} setUser={setUser} onLogout={logout} />
  ) : (
    <AccessForm onAuthenticated={setUser} />
  );
}

createRoot(document.getElementById("root")).render(<ThemeProvider theme={theme}><CssBaseline /><App /></ThemeProvider>);
