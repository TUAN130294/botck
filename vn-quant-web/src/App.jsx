import { useState, useEffect, useRef } from 'react'
import { createChart, ColorType, CandlestickSeries } from 'lightweight-charts'

const API_URL = 'http://localhost:8003/api'

const fmtMoney = (n) => new Intl.NumberFormat('vi-VN').format(n)

// --- Stock Chart Component (Compatible with lightweight-charts v5) ---
function StockChart({ data }) {
  const chartContainerRef = useRef(null)
  const chartRef = useRef(null)

  useEffect(() => {
    if (!data || data.length === 0 || !chartContainerRef.current) return

    // Cleanup previous chart
    if (chartRef.current) {
      chartRef.current.remove()
      chartRef.current = null
    }

    try {
      const chart = createChart(chartContainerRef.current, {
        layout: {
          background: { type: ColorType.Solid, color: 'transparent' },
          textColor: '#94a3b8'
        },
        grid: {
          vertLines: { color: 'rgba(255,255,255,0.05)' },
          horzLines: { color: 'rgba(255,255,255,0.05)' }
        },
        width: chartContainerRef.current.clientWidth || 600,
        height: 400,
      })
      chartRef.current = chart

      // v5 API: Use addSeries with CandlestickSeries type
      const candlestickSeries = chart.addSeries(CandlestickSeries, {
        upColor: '#0bda5e',
        downColor: '#ef4444',
        borderVisible: false,
        wickUpColor: '#0bda5e',
        wickDownColor: '#ef4444',
      })

      // Safely parse and filter data
      const chartData = data
        .filter(d => d.date && d.open && d.high && d.low && d.close)
        .map(d => ({
          time: String(d.date).split('T')[0],
          open: Number(d.open),
          high: Number(d.high),
          low: Number(d.low),
          close: Number(d.close)
        }))
        .sort((a, b) => a.time.localeCompare(b.time))

      if (chartData.length > 0) {
        candlestickSeries.setData(chartData)
        chart.timeScale().fitContent()
      }

      const handleResize = () => {
        if (chartContainerRef.current && chartRef.current) {
          chartRef.current.applyOptions({ width: chartContainerRef.current.clientWidth })
        }
      }
      window.addEventListener('resize', handleResize)

      return () => {
        window.removeEventListener('resize', handleResize)
        if (chartRef.current) {
          chartRef.current.remove()
          chartRef.current = null
        }
      }
    } catch (err) {
      console.error('Chart error:', err)
    }
  }, [data])

  return <div ref={chartContainerRef} className="w-full h-[400px] min-h-[400px]" />
}



// --- Sidebar ---
function Sidebar({ activeView, setView }) {
  const menuItems = [
    { id: 'dashboard', icon: 'dashboard', label: 'Overview' },
    { id: 'analysis', icon: 'show_chart', label: 'Analysis' },
    { id: 'news', icon: 'newspaper', label: 'News Intel' },
    { id: 'radar', icon: 'radar', label: 'Agent Radar' },
    { id: 'command', icon: 'forum', label: 'Agent Chat' },
    { id: 'trading', icon: 'account_balance', label: 'Auto Trading' },
    { id: 'backtest', icon: 'history', label: 'Backtest' },
    { id: 'predict', icon: 'auto_graph', label: 'AI Predict' },
    { id: 'data', icon: 'database', label: 'Data Hub' },
  ]

  return (
    <aside className="glass-sidebar w-72 h-full flex-shrink-0 flex flex-col justify-between py-6 px-4 hidden md:flex z-50">
      <div className="flex flex-col gap-8">
        <div className="flex items-center gap-3 px-2">
          <div className="relative flex items-center justify-center size-10 rounded-lg bg-gradient-to-br from-primary to-accent-cyan shadow-lg shadow-primary/20">
            <span className="material-symbols-outlined text-white text-[24px]">token</span>
          </div>
          <div className="flex flex-col">
            <h1 className="text-white text-xl font-bold tracking-tight">VN-QUANT</h1>
            <p className="text-slate-400 text-xs font-medium tracking-wide">AGENTIC LEVEL 4</p>
          </div>
        </div>

        <nav className="flex flex-col gap-2">
          <div className="px-3 py-1 text-xs font-bold text-slate-500 uppercase tracking-widest">Platform</div>
          {menuItems.map(item => (
            <button key={item.id} onClick={() => setView(item.id)}
              className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all group w-full text-left
                 ${activeView === item.id ? 'bg-primary/15 border border-primary/20 text-white shadow-sm' : 'hover:bg-white/5 text-slate-400 hover:text-white'}`}>
              <span className={`material-symbols-outlined transition-colors ${activeView === item.id ? 'text-primary' : 'group-hover:text-accent-cyan'}`}>{item.icon}</span>
              <span className="text-sm font-semibold">{item.label}</span>
            </button>
          ))}
        </nav>
      </div>

      <div className="flex flex-col gap-2">
        <div className="mt-4 flex items-center gap-3 px-4 py-3 rounded-xl bg-white/5 border border-white/5">
          <div className="size-8 rounded-full bg-gray-600 flex items-center justify-center text-xs font-bold">AD</div>
          <div className="flex flex-col">
            <span className="text-white text-sm font-bold">Admin</span>
            <span className="text-emerald-400 text-xs flex items-center gap-1">
              <span className="size-1.5 rounded-full bg-emerald-400 animate-pulse"></span>Online
            </span>
          </div>
        </div>
      </div>
    </aside>
  )
}

// --- Dashboard View ---
function DashboardView({ marketStatus, regime }) {
  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="glass-panel p-5 rounded-xl flex flex-col justify-between group hover:border-primary/40 transition-all">
          <div className="flex justify-between items-start">
            <div>
              <p className="text-slate-400 text-sm font-medium mb-1">VN-INDEX</p>
              <h3 className="text-2xl font-bold text-white tracking-tight">{marketStatus?.vnindex || 'Loading...'}</h3>
            </div>
            <div className="p-2 bg-primary/10 rounded-lg text-primary"><span className="material-symbols-outlined text-[20px]">show_chart</span></div>
          </div>
          <div className="mt-4 flex items-center gap-2">
            <span className={`${marketStatus?.change >= 0 ? 'text-emerald-400' : 'text-red-400'} text-sm font-bold flex items-center`}>
              <span className="material-symbols-outlined text-[16px]">{marketStatus?.change >= 0 ? 'trending_up' : 'trending_down'}</span>
              {marketStatus?.change > 0 ? '+' : ''}{marketStatus?.change} ({marketStatus?.change_pct}%)
            </span>
          </div>
        </div>

        <div className="glass-panel p-5 rounded-xl flex flex-col justify-between group hover:border-primary/40 transition-all">
          <div className="flex justify-between items-start">
            <div>
              <p className="text-slate-400 text-sm font-medium mb-1">Market Regime</p>
              <h3 className="text-2xl font-bold text-white tracking-tight">{regime?.regime || '---'}</h3>
            </div>
            <div className="p-2 bg-amber-500/10 rounded-lg text-amber-500"><span className="material-symbols-outlined text-[20px]">psychology</span></div>
          </div>
          <div className="mt-4">
            <span className="text-slate-400 text-xs">Hurst: {regime?.hurst_exponent?.toFixed(3) || '---'}</span>
            <span className="text-slate-400 text-xs ml-2">Conf: {((regime?.confidence || 0) * 100).toFixed(0)}%</span>
          </div>
        </div>

        <div className="glass-panel p-5 rounded-xl flex flex-col justify-between group hover:border-primary/40 transition-all">
          <div className="flex justify-between items-start">
            <div>
              <p className="text-slate-400 text-sm font-medium mb-1">Circuit Breaker</p>
              <h3 className="text-2xl font-bold text-white tracking-tight">NORMAL</h3>
            </div>
            <div className="p-2 bg-emerald-500/10 rounded-lg text-emerald-500"><span className="material-symbols-outlined text-[20px]">verified_user</span></div>
          </div>
          <div className="mt-4"><span className="text-emerald-400 text-xs font-bold">ALL SYSTEMS GO</span></div>
        </div>

        <div className="glass-panel p-5 rounded-xl flex flex-col justify-between group hover:border-primary/40 transition-all">
          <div className="flex justify-between items-start">
            <div>
              <p className="text-slate-400 text-sm font-medium mb-1">Active Agents</p>
              <h3 className="text-2xl font-bold text-white tracking-tight">8 <span className="text-lg text-slate-500 font-normal">/ 8</span></h3>
            </div>
            <div className="p-2 bg-accent-cyan/10 rounded-lg text-accent-cyan"><span className="material-symbols-outlined text-[20px]">smart_toy</span></div>
          </div>
          <div className="mt-4"><span className="text-emerald-400 text-xs font-bold">MADDPG ONLINE</span></div>
        </div>
      </section>

      <section className="glass-panel p-6 rounded-xl">
        <h2 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
          <span className="material-symbols-outlined text-primary">recommend</span> Recommended Strategies
        </h2>
        <div className="flex flex-wrap gap-2">
          {(regime?.recommended_strategies || ['Loading...']).map((s, i) => (
            <span key={i} className="px-4 py-2 bg-primary/10 text-primary rounded-full text-sm font-medium border border-primary/20">{s}</span>
          ))}
        </div>
      </section>
    </div>
  )
}

// --- Analysis View ---
function AnalysisView({ symbol, setSymbol, stockData }) {
  const [inputSym, setInputSym] = useState(symbol)
  const handleSearch = (e) => { if (e.key === 'Enter') setSymbol(inputSym) }
  const latest = stockData && stockData.length > 0 ? stockData[stockData.length - 1] : null

  return (
    <div className="flex-1 overflow-y-auto p-4 lg:p-6 pb-20">
      <div className="max-w-[1600px] mx-auto space-y-6">
        <div className="flex flex-col md:flex-row gap-6 md:items-end justify-between">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <input value={inputSym} onChange={(e) => setInputSym(e.target.value.toUpperCase())} onKeyDown={handleSearch}
                className="bg-transparent text-3xl md:text-4xl font-bold text-white tracking-tight border-b border-white/10 focus:border-primary focus:outline-none w-[200px]" />
              <span className="bg-white/5 text-slate-400 text-xs px-2 py-1 rounded border border-white/10">HOSE</span>
            </div>
            {latest ? (
              <div className="flex items-baseline gap-4">
                <span className="text-4xl font-bold text-white tracking-tight">{fmtMoney(latest.close)} <span className="text-lg text-slate-400 font-normal">VND</span></span>
              </div>
            ) : (<div className="text-slate-500">Loading data for {symbol}...</div>)}
          </div>
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
          <div className="xl:col-span-8 glass-panel rounded-xl overflow-hidden shadow-2xl shadow-black/40 p-2">
            {stockData && stockData.length > 0 ? <StockChart data={stockData} /> : <div className="flex items-center justify-center h-[400px] text-slate-500">Waiting for Data...</div>}
          </div>

          <div className="xl:col-span-4 flex flex-col gap-4">
            <h2 className="text-lg font-bold text-white flex items-center gap-2"><span className="material-symbols-outlined text-primary">groups</span> AI Agent Council</h2>
            <div className="glass-panel p-5 rounded-xl border-l-4 border-l-primary">
              <div className="flex items-center gap-3 mb-3">
                <div className="size-10 rounded-full bg-gradient-to-br from-primary to-blue-700 flex items-center justify-center shadow-lg"><span className="material-symbols-outlined text-white text-[20px]">manage_search</span></div>
                <div><h3 className="font-bold text-white text-base">Deep Flow AI</h3><p className="text-xs text-primary font-medium">Scanning: {symbol}</p></div>
              </div>
              <button className="w-full bg-white/10 hover:bg-white/20 text-white font-medium py-2 rounded-lg transition-colors border border-white/10"
                onClick={() => { fetch(`${API_URL}/analyze/deep_flow`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ symbol, days: 60 }) }).then(res => res.json()).then(d => alert(`Deep Flow: ${d.insights?.length || 0} signals found!`)) }}>
                Start Deep Scan
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

// --- Radar View (Agent Status) ---
function RadarView() {
  const [agents, setAgents] = useState([])

  useEffect(() => {
    fetch(`${API_URL}/agents/status`).then(r => r.json()).then(d => setAgents(d.agents || []))
  }, [])

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      <h2 className="text-2xl font-bold text-white flex items-center gap-2"><span className="material-symbols-outlined text-accent-cyan">radar</span> Agent Radar (MADDPG)</h2>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {agents.map((agent, i) => (
          <div key={i} className="glass-panel p-5 rounded-xl border-l-4 border-l-primary hover:border-l-accent-cyan transition-all">
            <div className="flex justify-between items-start mb-3">
              <div className="flex items-center gap-3">
                <div className="size-10 rounded-full bg-primary/20 flex items-center justify-center"><span className="material-symbols-outlined text-primary">smart_toy</span></div>
                <div>
                  <h3 className="font-bold text-white">{agent.name || agent.agent}</h3>
                  <span className={`text-xs flex items-center gap-1 ${agent.status === 'online' ? 'text-emerald-400' : 'text-slate-500'}`}>
                    <span className={`size-1.5 rounded-full ${agent.status === 'online' ? 'bg-emerald-400 animate-pulse' : 'bg-slate-600'}`}></span>
                    {agent.status || agent.role}
                  </span>
                </div>
              </div>
              <span className="text-2xl font-bold text-white">{((agent.accuracy || agent.win_rate || 0) * 100).toFixed(0)}%</span>
            </div>
            <div className="h-1.5 bg-white/10 rounded-full overflow-hidden mb-2"><div className="h-full bg-primary rounded-full" style={{ width: `${(agent.accuracy || agent.win_rate || 0.5) * 100}%` }}></div></div>
            <p className="text-sm text-slate-400">{agent.last_signal || `Role: ${agent.role}`}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

// --- Command Center View (Agent Communication Feed) ---
function CommandView() {
  const [symbol, setSymbol] = useState('MWG')
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)

  const runAgentAnalysis = async () => {
    setLoading(true)
    setMessages([])

    try {
      const resp = await fetch(`${API_URL}/agents/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol })
      })
      const data = await resp.json()
      setMessages(data.messages || [])
    } catch (err) {
      setMessages([{ sender: 'System', emoji: '❌', content: 'Error connecting to AI agents', type: 'ERROR' }])
    }

    setLoading(false)
  }

  const getTypeColor = (type) => {
    switch (type) {
      case 'SUCCESS': return 'bg-emerald-500/20 text-emerald-400'
      case 'WARNING': return 'bg-amber-500/20 text-amber-400'
      case 'ERROR': return 'bg-red-500/20 text-red-400'
      default: return 'bg-blue-500/20 text-blue-400'
    }
  }

  const getSenderColor = (sender) => {
    switch (sender) {
      case 'Scout': return 'border-l-cyan-400'
      case 'Alex': return 'border-l-blue-400'
      case 'Bull': return 'border-l-emerald-400'
      case 'Bear': return 'border-l-red-400'
      case 'Chief': return 'border-l-purple-400 bg-purple-500/5'
      default: return 'border-l-slate-400'
    }
  }

  return (
    <div className="flex-1 flex flex-col p-6 overflow-hidden">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-2xl font-bold text-white flex items-center gap-2">
          <span className="material-symbols-outlined text-accent-pink">forum</span>
          Agent Communication Feed
          <span className="text-xs px-2 py-1 bg-red-500/20 text-red-400 rounded-full animate-pulse">● LIVE AI</span>
        </h2>
      </div>

      {/* Control Panel */}
      <div className="glass-panel p-4 rounded-xl mb-4 flex gap-4 items-center">
        <input
          value={symbol}
          onChange={(e) => setSymbol(e.target.value.toUpperCase())}
          className="bg-white/5 border border-white/10 rounded-lg px-4 py-2 text-white w-32 focus:outline-none focus:border-primary"
          placeholder="Symbol"
        />
        <button
          onClick={runAgentAnalysis}
          disabled={loading}
          className={`flex-1 py-3 rounded-xl font-bold transition-all flex items-center justify-center gap-2
            ${loading ? 'bg-white/10 text-slate-400 cursor-not-allowed' : 'bg-gradient-to-r from-primary to-purple-600 text-white hover:shadow-lg'}`}
        >
          {loading ? (
            <>
              <span className="animate-spin">⟳</span> Đang phân tích với AI...
            </>
          ) : (
            <>
              <span className="material-symbols-outlined">rocket_launch</span>
              PHÂN TÍCH VỚI AI (5 Agents)
            </>
          )}
        </button>
      </div>

      {/* Agent Stats */}
      <div className="grid grid-cols-5 gap-2 mb-4">
        {[
          { name: 'Scout', emoji: '🔭', color: 'text-cyan-400' },
          { name: 'Alex', emoji: '📊', color: 'text-blue-400' },
          { name: 'Bull', emoji: '🐂', color: 'text-emerald-400' },
          { name: 'Bear', emoji: '🐻', color: 'text-red-400' },
          { name: 'Chief', emoji: '👔', color: 'text-purple-400' },
        ].map(agent => (
          <div key={agent.name} className="glass-panel p-3 rounded-lg text-center">
            <span className="text-2xl">{agent.emoji}</span>
            <p className={`text-sm font-bold ${agent.color}`}>{agent.name}</p>
          </div>
        ))}
      </div>

      {/* Message Feed */}
      <div className="flex-1 glass-panel rounded-xl p-4 overflow-y-auto space-y-3">
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full text-slate-500">
            <div className="text-center">
              <span className="material-symbols-outlined text-6xl mb-2">smart_toy</span>
              <p>Nhập mã cổ phiếu và click <strong>PHÂN TÍCH VỚI AI</strong></p>
              <p className="text-sm">5 AI Agents sẽ thảo luận và đưa ra quyết định</p>
            </div>
          </div>
        ) : (
          messages.map((msg, i) => (
            <div key={i} className={`p-4 rounded-xl border-l-4 ${getSenderColor(msg.sender)} bg-white/5 animate-fade-in`}>
              <div className="flex justify-between items-start mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-xl">{msg.emoji}</span>
                  <span className="font-bold text-white">{msg.sender}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-500">{msg.time}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${getTypeColor(msg.type)}`}>{msg.type}</span>
                </div>
              </div>
              <div className="text-slate-200 leading-relaxed whitespace-pre-wrap">{msg.content}</div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}


// --- Backtest View ---
function BacktestView() {
  const strategies = [
    { name: 'Momentum + MADDPG', winRate: 65.4, profitFactor: 2.14, maxDrawdown: -4.2, sharpe: 1.85 },
    { name: 'Mean Reversion', winRate: 58.2, profitFactor: 1.85, maxDrawdown: -6.8, sharpe: 1.52 },
    { name: 'Cooperative Ensemble', winRate: 72.1, profitFactor: 2.45, maxDrawdown: -3.1, sharpe: 2.12 },
  ]

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      <h2 className="text-2xl font-bold text-white flex items-center gap-2"><span className="material-symbols-outlined text-amber-400">history</span> Walk-Forward Backtest</h2>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {strategies.map((s, i) => (
          <div key={i} className="glass-panel p-6 rounded-xl">
            <h3 className="text-lg font-bold text-white mb-4">{s.name}</h3>
            <div className="grid grid-cols-2 gap-4">
              <div><p className="text-slate-500 text-xs mb-1">Win Rate</p><p className="text-2xl font-bold text-emerald-400">{s.winRate}%</p></div>
              <div><p className="text-slate-500 text-xs mb-1">Sharpe Ratio</p><p className="text-2xl font-bold text-white">{s.sharpe}</p></div>
              <div><p className="text-slate-500 text-xs mb-1">Max Drawdown</p><p className="text-2xl font-bold text-red-400">{s.maxDrawdown}%</p></div>
              <div><p className="text-slate-500 text-xs mb-1">Profit Factor</p><p className="text-2xl font-bold text-emerald-400">{s.profitFactor}</p></div>
            </div>
            <button className="w-full mt-4 bg-white/10 hover:bg-white/20 text-white py-2 rounded-lg transition-colors border border-white/10">Run Backtest</button>
          </div>
        ))}
      </div>
    </div>
  )
}

// --- Predict View (Stockformer) ---
function PredictView({ symbol }) {
  const [prediction, setPrediction] = useState(null)
  const [loading, setLoading] = useState(false)

  const runPrediction = () => {
    setLoading(true)
    fetch(`${API_URL}/predict/${symbol}`).then(r => r.json()).then(d => { setPrediction(d); setLoading(false) })
  }

  useEffect(() => { runPrediction() }, [symbol])

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      <h2 className="text-2xl font-bold text-white flex items-center gap-2"><span className="material-symbols-outlined text-accent-pink">auto_graph</span> Stockformer AI Prediction</h2>

      <div className="glass-panel p-6 rounded-xl">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-3xl font-bold text-white">{symbol}</h3>
            <p className="text-slate-400">Current: {fmtMoney(prediction?.current_price || 0)} VND</p>
          </div>
          <div className={`px-6 py-3 rounded-xl font-bold text-xl ${prediction?.direction === 'UP' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'}`}>
            {prediction?.direction || '---'}
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-white/5 p-4 rounded-lg"><p className="text-slate-500 text-xs">Expected Return</p><p className="text-2xl font-bold text-white">{prediction?.expected_return?.toFixed(2) || '---'}%</p></div>
          <div className="bg-white/5 p-4 rounded-lg"><p className="text-slate-500 text-xs">Confidence</p><p className="text-2xl font-bold text-white">{((prediction?.confidence || 0) * 100).toFixed(0)}%</p></div>
          <div className="bg-white/5 p-4 rounded-lg"><p className="text-slate-500 text-xs">Volatility</p><p className="text-2xl font-bold text-white">{prediction?.volatility_forecast?.toFixed(4) || '---'}</p></div>
          <div className="bg-white/5 p-4 rounded-lg"><p className="text-slate-500 text-xs">Model</p><p className="text-lg font-bold text-primary">{prediction?.model || 'Loading'}</p></div>
        </div>

        <div>
          <h4 className="text-white font-bold mb-2">5-Day Price Forecast</h4>
          <div className="flex gap-2">
            {(prediction?.predictions || []).map((p, i) => (
              <div key={i} className="flex-1 bg-white/5 p-3 rounded-lg text-center">
                <p className="text-slate-500 text-xs">Day {i + 1}</p>
                <p className="text-white font-bold">{fmtMoney(p)}</p>
              </div>
            ))}
          </div>
        </div>

        <button onClick={runPrediction} disabled={loading} className="mt-6 bg-primary hover:bg-blue-600 text-white px-6 py-3 rounded-xl font-bold transition-all w-full">
          {loading ? 'Predicting...' : 'Refresh Prediction'}
        </button>
      </div>
    </div>
  )
}

// --- DataHub View ---
function DataHubView() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch(`${API_URL}/data/stats`).then(r => r.json()).then(d => { setStats(d); setLoading(false) })
  }, [])

  if (loading) return <div className="flex-1 flex items-center justify-center text-white">Loading data stats...</div>

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      <h2 className="text-2xl font-bold text-white flex items-center gap-2">
        <span className="material-symbols-outlined text-accent-cyan">database</span> Data Hub
        <span className="text-xs px-2 py-1 bg-emerald-500/20 text-emerald-400 rounded-full">Auto Update 17:30</span>
      </h2>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="glass-panel p-6 rounded-xl text-center">
          <div className="text-4xl font-bold text-primary">{stats?.total_files || 0}</div>
          <div className="text-slate-400 text-sm">Mã cổ phiếu đã tải</div>
        </div>
        <div className="glass-panel p-6 rounded-xl text-center">
          <div className="text-4xl font-bold text-emerald-400">{stats?.total_available || 1730}</div>
          <div className="text-slate-400 text-sm">Tổng mã toàn sàn</div>
        </div>
        <div className="glass-panel p-6 rounded-xl text-center">
          <div className="text-4xl font-bold text-amber-400">{stats?.coverage_pct || 0}%</div>
          <div className="text-slate-400 text-sm">Coverage</div>
        </div>
        <div className="glass-panel p-6 rounded-xl text-center">
          <div className="text-4xl font-bold text-white">{stats?.total_size_mb || 0} MB</div>
          <div className="text-slate-400 text-sm">Dung lượng</div>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="glass-panel p-6 rounded-xl">
        <div className="flex justify-between mb-2">
          <span className="text-white font-bold">Data Coverage</span>
          <span className="text-primary">{stats?.total_files}/{stats?.total_available}</span>
        </div>
        <div className="h-4 bg-white/10 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-primary to-emerald-400 rounded-full transition-all"
            style={{ width: `${stats?.coverage_pct || 0}%` }}
          ></div>
        </div>
        <p className="text-slate-400 text-sm mt-2">
          {stats?.coverage_pct < 100
            ? `Đang tải thêm... Chạy "python download_all_stocks.py" để tải đầy đủ.`
            : '✅ Đã tải đầy đủ toàn sàn!'}
        </p>
      </div>

      {/* Auto Update Info */}
      <div className="glass-panel p-6 rounded-xl border-l-4 border-l-emerald-400">
        <h3 className="text-white font-bold mb-2 flex items-center gap-2">
          <span className="material-symbols-outlined text-emerald-400">schedule</span>
          Tự động cập nhật
        </h3>
        <p className="text-slate-300">Data được cập nhật tự động lúc <strong>17:30</strong> hàng ngày sau khi thị trường đóng cửa.</p>
        <p className="text-slate-400 text-sm mt-1">Task Scheduler: VN-QUANT-DataUpdate</p>
      </div>

      {/* Sample Symbols */}
      <div className="glass-panel p-6 rounded-xl">
        <h3 className="text-white font-bold mb-4">Mã cổ phiếu đã tải (mẫu)</h3>
        <div className="flex flex-wrap gap-2">
          {(stats?.sample_symbols || []).map(s => (
            <span key={s} className="px-3 py-1 bg-white/5 text-white rounded-full text-sm border border-white/10">{s}</span>
          ))}
        </div>
      </div>
    </div>
  )
}

// --- News Intelligence View ---
function NewsIntelView() {
  const [status, setStatus] = useState(null)
  const [alerts, setAlerts] = useState([])
  const [mood, setMood] = useState(null)
  const [scanning, setScanning] = useState(false)
  const [watchlist, setWatchlist] = useState([])
  const [newSymbol, setNewSymbol] = useState('')

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 60000) // Refresh every minute
    return () => clearInterval(interval)
  }, [])

  const loadData = async () => {
    try {
      const [statusRes, alertsRes, moodRes, watchlistRes] = await Promise.all([
        fetch(`${API_URL}/news/status`).then(r => r.json()),
        fetch(`${API_URL}/news/alerts`).then(r => r.json()),
        fetch(`${API_URL}/news/market-mood`).then(r => r.json()),
        fetch(`${API_URL}/news/watchlist`).then(r => r.json())
      ])
      setStatus(statusRes)
      setAlerts(alertsRes.alerts || [])
      setMood(moodRes)
      setWatchlist(watchlistRes.watchlist || [])
    } catch (e) {
      console.error('Load error:', e)
    }
  }

  const runScan = async () => {
    setScanning(true)
    try {
      const res = await fetch(`${API_URL}/news/scan`, { method: 'POST' })
      const data = await res.json()
      if (data.alerts) {
        setAlerts(data.alerts)
      }
    } catch (e) {
      console.error('Scan error:', e)
    }
    setScanning(false)
    loadData()
  }

  const addToWatchlist = async () => {
    if (!newSymbol.trim()) return
    const updated = [...watchlist, newSymbol.toUpperCase()]
    try {
      await fetch(`${API_URL}/news/watchlist`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updated)
      })
      setWatchlist(updated)
      setNewSymbol('')
    } catch (e) { }
  }

  const removeFromWatchlist = async (symbol) => {
    const updated = watchlist.filter(s => s !== symbol)
    try {
      await fetch(`${API_URL}/news/watchlist`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updated)
      })
      setWatchlist(updated)
    } catch (e) { }
  }

  const getMoodColor = (m) => {
    switch (m) {
      case 'bullish': return 'text-emerald-400 bg-emerald-400/20'
      case 'slightly_bullish': return 'text-green-400 bg-green-400/20'
      case 'bearish': return 'text-red-400 bg-red-400/20'
      case 'slightly_bearish': return 'text-orange-400 bg-orange-400/20'
      default: return 'text-slate-400 bg-slate-400/20'
    }
  }

  const getPriorityColor = (p) => {
    switch (p) {
      case 'CRITICAL': return 'bg-red-500/20 text-red-400 border-red-500'
      case 'HIGH': return 'bg-orange-500/20 text-orange-400 border-orange-500'
      case 'MEDIUM': return 'bg-yellow-500/20 text-yellow-400 border-yellow-500'
      default: return 'bg-slate-500/20 text-slate-400 border-slate-500'
    }
  }

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-white flex items-center gap-2">
          <span className="material-symbols-outlined text-accent-cyan">newspaper</span>
          News Intelligence
          <span className="text-xs px-2 py-1 bg-purple-500/20 text-purple-400 rounded-full ml-2">
            Tin tức TRƯỚC - Giá SAU
          </span>
        </h2>
        <button
          onClick={runScan}
          disabled={scanning}
          className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-primary to-accent-cyan text-white rounded-lg hover:opacity-90 disabled:opacity-50"
        >
          <span className={`material-symbols-outlined ${scanning ? 'animate-spin' : ''}`}>
            {scanning ? 'sync' : 'radar'}
          </span>
          {scanning ? 'Đang quét...' : 'Scan Now'}
        </button>
      </div>

      {/* Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Market Mood */}
        <div className="glass-panel p-6 rounded-xl">
          <div className="text-slate-400 text-sm mb-1">Market Mood</div>
          <div className={`text-2xl font-bold ${getMoodColor(mood?.mood)} px-3 py-1 rounded-lg inline-block`}>
            {mood?.mood?.toUpperCase() || 'LOADING...'}
          </div>
          <div className="text-slate-500 text-xs mt-2">
            Score: {mood?.score?.toFixed(2) || 0} | {mood?.news_count || 0} tin
          </div>
        </div>

        {/* Watchlist */}
        <div className="glass-panel p-6 rounded-xl">
          <div className="text-slate-400 text-sm mb-1">Watchlist</div>
          <div className="text-3xl font-bold text-white">{watchlist.length}</div>
          <div className="text-slate-500 text-xs">mã theo dõi</div>
        </div>

        {/* Today Alerts */}
        <div className="glass-panel p-6 rounded-xl">
          <div className="text-slate-400 text-sm mb-1">Alerts Hôm nay</div>
          <div className="text-3xl font-bold text-accent-cyan">{alerts.length}</div>
          <div className="text-slate-500 text-xs">
            {alerts.filter(a => a.priority === 'CRITICAL' || a.priority === 'HIGH').length} quan trọng
          </div>
        </div>

        {/* Last Scan */}
        <div className="glass-panel p-6 rounded-xl">
          <div className="text-slate-400 text-sm mb-1">Lần quét cuối</div>
          <div className="text-lg font-bold text-white">
            {status?.last_scan ? new Date(status.last_scan).toLocaleTimeString() : '--:--:--'}
          </div>
          <div className={`text-xs mt-1 ${status?.telegram_enabled ? 'text-emerald-400' : 'text-slate-500'}`}>
            {status?.telegram_enabled ? '✅ Telegram ON' : '📱 Telegram OFF'}
          </div>
        </div>
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Alerts Panel */}
        <div className="lg:col-span-2 glass-panel p-6 rounded-xl">
          <h3 className="text-white font-bold mb-4 flex items-center gap-2">
            <span className="material-symbols-outlined text-red-400">notifications_active</span>
            News Alerts
          </h3>

          {alerts.length === 0 ? (
            <div className="text-slate-400 text-center py-10">
              Không có alerts. Nhấn "Scan Now" để quét tin tức.
            </div>
          ) : (
            <div className="space-y-3 max-h-[400px] overflow-y-auto">
              {alerts.map((alert, idx) => (
                <div key={idx} className={`p-4 rounded-lg border-l-4 ${getPriorityColor(alert.priority)}`}>
                  <div className="flex justify-between items-start mb-2">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-white text-lg">{alert.symbol}</span>
                      <span className={`text-xs px-2 py-0.5 rounded ${getPriorityColor(alert.priority)}`}>
                        {alert.priority}
                      </span>
                      <span className="text-xs px-2 py-0.5 bg-white/10 text-slate-300 rounded">
                        {alert.type}
                      </span>
                    </div>
                    <span className="text-xs text-slate-500">
                      {new Date(alert.timestamp).toLocaleTimeString()}
                    </span>
                  </div>

                  <div className="text-slate-300 text-sm mb-2">
                    📰 {alert.news_summary || 'N/A'}
                  </div>

                  <div className="text-slate-400 text-sm mb-2">
                    📊 {alert.technical_summary || 'Chưa có dữ liệu kỹ thuật'}
                  </div>

                  <div className="text-white font-medium">
                    ➡️ {alert.recommendation}
                  </div>

                  <div className="flex items-center justify-between gap-4 mt-2 text-xs text-slate-500">
                    <div className="flex gap-4">
                      <span>Sentiment: {(alert.news_sentiment || 0).toFixed(2)}</span>
                      <span>Confidence: {((alert.confidence || 0) * 100).toFixed(0)}%</span>
                    </div>
                    {alert.url && (
                      <a
                        href={alert.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary hover:text-primary/80 underline flex items-center gap-1"
                      >
                        <span className="material-symbols-outlined text-xs">open_in_new</span>
                        Đọc tin
                      </a>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Watchlist Panel */}
        <div className="glass-panel p-6 rounded-xl">
          <h3 className="text-white font-bold mb-4 flex items-center gap-2">
            <span className="material-symbols-outlined text-primary">visibility</span>
            Watchlist
          </h3>

          {/* Add Symbol */}
          <div className="flex gap-2 mb-4">
            <input
              type="text"
              value={newSymbol}
              onChange={(e) => setNewSymbol(e.target.value.toUpperCase())}
              placeholder="VNM, HPG..."
              className="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
              onKeyDown={(e) => e.key === 'Enter' && addToWatchlist()}
            />
            <button
              onClick={addToWatchlist}
              className="px-3 py-2 bg-primary text-white rounded-lg hover:bg-primary/80"
            >
              <span className="material-symbols-outlined">add</span>
            </button>
          </div>

          {/* Symbol List */}
          <div className="flex flex-wrap gap-2 max-h-[300px] overflow-y-auto">
            {watchlist.map(symbol => (
              <span key={symbol} className="group px-3 py-1 bg-white/5 text-white rounded-full text-sm border border-white/10 hover:border-primary transition-all flex items-center gap-1">
                {symbol}
                <button
                  onClick={() => removeFromWatchlist(symbol)}
                  className="opacity-0 group-hover:opacity-100 text-red-400 hover:text-red-300"
                >
                  ×
                </button>
              </span>
            ))}
          </div>

          {watchlist.length === 0 && (
            <div className="text-slate-500 text-center py-4">
              Thêm mã vào watchlist để theo dõi tin tức
            </div>
          )}
        </div>
      </div>

      {/* Info Panel */}
      <div className="glass-panel p-6 rounded-xl border-l-4 border-l-purple-400">
        <h3 className="text-white font-bold mb-2 flex items-center gap-2">
          <span className="material-symbols-outlined text-purple-400">info</span>
          Cách hoạt động
        </h3>
        <div className="text-slate-300 space-y-2">
          <p>📰 <strong>Bước 1:</strong> Hệ thống quét tin tức từ CafeF, VietStock, TCBS mỗi 5 phút</p>
          <p>🤖 <strong>Bước 2:</strong> AI phân tích sentiment (tích cực/tiêu cực) và impact (quan trọng/bình thường)</p>
          <p>📊 <strong>Bước 3:</strong> Khi có tin quan trọng → Quét kỹ thuật cho mã đó</p>
          <p>🔔 <strong>Bước 4:</strong> Gửi alert qua Telegram nếu có signal mạnh</p>
          <p className="text-purple-400 font-medium mt-3">💡 Đặc điểm: Tin tức TRƯỚC - Phản ứng giá SAU → Bạn biết trước thị trường!</p>
        </div>
      </div>
    </div>
  )
}

// --- Autonomous Trading View (Port 8001) ---
function TradingView() {
  const [agentMessages, setAgentMessages] = useState([])
  const [orders, setOrders] = useState([])
  const [positions, setPositions] = useState([])
  const [trades, setTrades] = useState([])
  const [wsConnected, setWsConnected] = useState(false)
  const wsRef = useRef(null)

  useEffect(() => {
    // Connect to WebSocket on port 8001
    connectWebSocket()
    // Fetch initial data
    fetchOrders()
    fetchPositions()
    fetchTrades()

    return () => {
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [])

  const connectWebSocket = () => {
    const ws = new WebSocket('ws://localhost:8001/ws/autonomous')

    ws.onopen = () => {
      console.log('✅ WebSocket connected to autonomous trading system')
      setWsConnected(true)
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)

        if (data.type === 'agent_discussion') {
          // Add agent discussion to messages
          setAgentMessages(prev => [data, ...prev].slice(0, 50)) // Keep last 50
        } else if (data.type === 'order_executed') {
          // Refresh orders when new order is placed
          fetchOrders()
          fetchPositions()
        } else if (data.type === 'position_exited') {
          // Refresh when position exits
          fetchPositions()
          fetchTrades()
        }
      } catch (err) {
        console.error('WebSocket message error:', err)
      }
    }

    ws.onclose = () => {
      console.log('❌ WebSocket disconnected')
      setWsConnected(false)
      // Reconnect after 5 seconds
      setTimeout(connectWebSocket, 5000)
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
    }

    wsRef.current = ws
  }

  const fetchOrders = async () => {
    try {
      const resp = await fetch('http://localhost:8001/api/orders')
      const data = await resp.json()
      setOrders(data.orders || [])
    } catch (err) {
      console.error('Failed to fetch orders:', err)
    }
  }

  const fetchPositions = async () => {
    try {
      const resp = await fetch('http://localhost:8001/api/positions')
      const data = await resp.json()
      setPositions(data.positions || [])
    } catch (err) {
      console.error('Failed to fetch positions:', err)
    }
  }

  const fetchTrades = async () => {
    try {
      const resp = await fetch('http://localhost:8001/api/trades')
      const data = await resp.json()
      setTrades(data.trades || [])
    } catch (err) {
      console.error('Failed to fetch trades:', err)
    }
  }

  const triggerTestOpportunity = async () => {
    try {
      await fetch('http://localhost:8001/api/test/opportunity?symbol=ACB', { method: 'POST' })
    } catch (err) {
      console.error('Failed to trigger test:', err)
    }
  }

  const fmtVND = (n) => new Intl.NumberFormat('vi-VN').format(n)

  // Calculate portfolio value
  const totalPositionValue = positions.reduce((sum, pos) => sum + (pos.current_price * pos.quantity), 0)
  const totalCash = 100_000_000 - totalPositionValue // Simplified calculation
  const totalPnL = positions.reduce((sum, pos) => sum + pos.unrealized_pnl, 0)

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-white flex items-center gap-2">
          <span className="material-symbols-outlined text-amber-400">smart_toy</span>
          Giao dịch Tự động 100%
          <span className={`text-xs px-2 py-1 rounded-full ${wsConnected ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'}`}>
            {wsConnected ? '🟢 LIVE' : '🔴 OFFLINE'}
          </span>
        </h2>
        <button onClick={triggerTestOpportunity}
          className="px-4 py-2 bg-cyan-500/20 text-cyan-400 rounded-lg hover:bg-cyan-500/30 text-sm">
          🧪 Test Opportunity
        </button>
      </div>

      {/* Portfolio Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="glass-panel p-4 rounded-xl text-center">
          <div className="text-2xl font-bold text-white">{fmtVND(totalCash)}</div>
          <div className="text-slate-400 text-sm">Tiền mặt</div>
        </div>
        <div className="glass-panel p-4 rounded-xl text-center">
          <div className="text-2xl font-bold text-primary">{fmtVND(totalCash + totalPositionValue)}</div>
          <div className="text-slate-400 text-sm">Tổng tài sản</div>
        </div>
        <div className="glass-panel p-4 rounded-xl text-center">
          <div className={`text-2xl font-bold ${totalPnL >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
            {totalPnL >= 0 ? '+' : ''}{fmtVND(totalPnL)}
          </div>
          <div className="text-slate-400 text-sm">Lãi/Lỗ chưa thực hiện</div>
        </div>
        <div className="glass-panel p-4 rounded-xl text-center">
          <div className="text-2xl font-bold text-amber-400">{positions.length}</div>
          <div className="text-slate-400 text-sm">Vị thế hiện tại</div>
        </div>
      </div>

      {/* Agent Conversations */}
      <div className="glass-panel p-6 rounded-xl">
        <h3 className="text-white font-bold mb-4 flex items-center gap-2">
          <span className="material-symbols-outlined text-cyan-400">forum</span>
          Thảo luận của AI Agents ({agentMessages.length})
        </h3>
        <div className="space-y-4 max-h-[500px] overflow-y-auto">
          {agentMessages.length === 0 && (
            <p className="text-slate-500 text-center py-8">Chưa có thảo luận nào. Đang chờ cơ hội...</p>
          )}
          {agentMessages.map((discussion, idx) => (
            <div key={idx} className="bg-white/5 p-4 rounded-lg border border-white/10">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className="text-white font-bold text-lg">{discussion.symbol}</span>
                  <span className="text-xs px-2 py-1 bg-purple-500/20 text-purple-400 rounded-full">
                    {discussion.source}
                  </span>
                </div>
                <span className="text-xs text-slate-400">
                  {new Date(discussion.timestamp).toLocaleTimeString('vi-VN')}
                </span>
              </div>

              {/* Agent Messages */}
              <div className="space-y-3">
                {discussion.messages?.map((msg, msgIdx) => {
                  const agentName = msg.agent_name || msg.agent || 'Unknown'
                  const agentEmoji = msg.agent_emoji || '🤖'
                  let bgColor = 'rgba(0,255,136,0.08)'
                  let borderColor = '#00ff88'

                  if (agentName === 'Bull') {
                    bgColor = 'rgba(0,200,255,0.08)'
                    borderColor = '#00c8ff'
                  } else if (agentName === 'Bear') {
                    bgColor = 'rgba(255,100,100,0.08)'
                    borderColor = '#ff6464'
                  } else if (agentName === 'Chief') {
                    bgColor = 'rgba(255,200,0,0.08)'
                    borderColor = '#ffc800'
                  } else if (agentName === 'RiskDoctor') {
                    bgColor = 'rgba(150,100,255,0.08)'
                    borderColor = '#9664ff'
                  }

                  return (
                    <div key={msgIdx} style={{ background: bgColor, borderLeft: `4px solid ${borderColor}` }}
                      className="p-3 rounded-lg">
                      <div className="font-bold mb-2" style={{ color: borderColor }}>
                        {agentEmoji} {agentName}
                      </div>
                      <div className="text-slate-300 text-sm whitespace-pre-wrap" style={{ lineHeight: '1.6' }}>
                        {msg.content || msg.message || ''}
                      </div>
                    </div>
                  )
                })}
              </div>

              {/* Verdict */}
              {discussion.verdict && (
                <div className="mt-3 p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg">
                  <div className="text-amber-400 font-bold">
                    📋 Quyết định: {discussion.verdict.signal_type || 'N/A'}
                  </div>
                  <div className="text-slate-400 text-sm mt-1">
                    Độ tin cậy: {(discussion.verdict.confidence * 100).toFixed(0)}%
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Positions */}
        <div className="glass-panel p-6 rounded-xl">
          <h3 className="text-white font-bold mb-4 flex items-center gap-2">
            <span className="material-symbols-outlined text-primary">inventory_2</span>
            Vị thế hiện tại ({positions.length})
          </h3>
          {positions.length > 0 ? (
            <div className="space-y-2 max-h-[300px] overflow-y-auto">
              {positions.map((pos, idx) => (
                <div key={idx} className="bg-white/5 p-3 rounded-lg">
                  <div className="flex justify-between items-start mb-2">
                    <div>
                      <span className="text-white font-bold">{pos.symbol}</span>
                      <span className="text-slate-400 text-sm ml-2">
                        {pos.quantity} @ {fmtVND(pos.avg_price)}
                      </span>
                    </div>
                    <div className={`font-bold ${pos.unrealized_pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                      {pos.unrealized_pnl >= 0 ? '+' : ''}{fmtVND(pos.unrealized_pnl)}
                    </div>
                  </div>
                  <div className="text-xs text-slate-500 flex items-center gap-2">
                    <span>TP: +{(pos.take_profit_pct * 100).toFixed(0)}%</span>
                    <span>•</span>
                    <span>Trail: {(pos.trailing_stop_pct * 100).toFixed(0)}%</span>
                    <span>•</span>
                    <span>SL: {(pos.stop_loss_pct * 100).toFixed(0)}%</span>
                    <span>•</span>
                    <span className={pos.can_sell ? 'text-emerald-400' : 'text-amber-400'}>
                      {pos.can_sell ? '✅ Có thể bán' : `⏳ T+${pos.trading_days_held || pos.days_held || 0}`}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-slate-500 text-center py-4">Chưa có vị thế nào</p>
          )}
        </div>

        {/* Recent Orders */}
        <div className="glass-panel p-6 rounded-xl">
          <h3 className="text-white font-bold mb-4 flex items-center gap-2">
            <span className="material-symbols-outlined text-amber-400">receipt_long</span>
            Lệnh gần đây ({orders.length})
          </h3>
          <div className="space-y-2 max-h-[300px] overflow-y-auto">
            {orders.slice(0, 10).map((order, idx) => (
              <div key={idx} className={`p-3 rounded-lg ${order.order_type === 'BUY' ? 'bg-emerald-500/10' : 'bg-red-500/10'}`}>
                <div className="flex justify-between items-center">
                  <div>
                    <span className={`font-bold ${order.order_type === 'BUY' ? 'text-emerald-400' : 'text-red-400'}`}>
                      {order.order_type === 'BUY' ? '📈 MUA' : '📉 BÁN'}
                    </span>
                    <span className="text-white ml-2">{order.symbol}</span>
                    <span className="text-slate-400 text-sm ml-2">
                      {order.quantity} @ {fmtVND(order.price)}
                    </span>
                  </div>
                  <span className="text-xs text-slate-500">
                    {new Date(order.timestamp).toLocaleTimeString('vi-VN')}
                  </span>
                </div>
              </div>
            ))}
            {orders.length === 0 && (
              <p className="text-slate-500 text-center py-4">Chưa có lệnh nào</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

// --- Main App ---
export default function App() {
  const [activeView, setActiveView] = useState('dashboard')
  const [marketStatus, setMarketStatus] = useState(null)
  const [regime, setRegime] = useState(null)
  const [symbol, setSymbol] = useState('HPG')
  const [stockData, setStockData] = useState([])

  useEffect(() => {
    fetch(`${API_URL}/market/status`).then(r => r.json()).then(d => setMarketStatus(d)).catch(e => console.error('Market status error:', e))
    fetch(`${API_URL}/analyze/regime/VNINDEX`).then(r => r.json()).then(d => setRegime(d)).catch(e => console.error('Regime error:', e))
  }, [])

  useEffect(() => {
    fetch(`${API_URL}/stock/${symbol}`).then(r => r.json()).then(d => setStockData(d))
  }, [symbol])

  return (
    <div className="relative flex h-screen w-screen bg-background-light dark:bg-background-dark overflow-hidden">
      <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
        <div className="absolute -top-[20%] -left-[10%] w-[50%] h-[50%] bg-primary/20 rounded-full blur-[120px] opacity-40 animate-pulse"></div>
        <div className="absolute top-[40%] -right-[10%] w-[40%] h-[40%] bg-accent-cyan/10 rounded-full blur-[100px] opacity-30"></div>
        <div className="absolute -bottom-[20%] left-[20%] w-[60%] h-[40%] bg-accent-pink/10 rounded-full blur-[120px] opacity-20"></div>
      </div>

      <Sidebar activeView={activeView} setView={setActiveView} />

      <main className="flex-1 flex flex-col min-w-0 h-full overflow-hidden relative z-10">
        <header className="glass-panel mx-6 mt-4 rounded-xl flex items-center justify-between px-6 py-3 z-20 shrink-0">
          <div className="flex items-center gap-6 overflow-hidden">
            <div className="flex items-center gap-2 text-primary shrink-0">
              <span className="material-symbols-outlined text-[20px] animate-pulse">ssid_chart</span>
              <span className="font-bold text-sm tracking-wide">AGENTIC LEVEL 4</span>
            </div>
            <div className="h-6 w-px bg-white/10 mx-2"></div>
            <div className="flex items-center gap-2">
              <span className="text-slate-400 font-medium">VN-INDEX</span>
              <span className="text-white font-bold">{marketStatus?.vnindex || '---'}</span>
              <span className={`text-xs font-mono px-1.5 py-0.5 rounded ${marketStatus?.change >= 0 ? 'text-emerald-400 bg-emerald-400/10' : 'text-red-400 bg-red-400/10'}`}>
                {marketStatus?.change > 0 ? '+' : ''}{marketStatus?.change}
              </span>
            </div>
          </div>
        </header>

        {activeView === 'dashboard' && <DashboardView marketStatus={marketStatus} regime={regime} />}
        {activeView === 'analysis' && <AnalysisView symbol={symbol} setSymbol={setSymbol} stockData={stockData} />}
        {activeView === 'news' && <NewsIntelView />}
        {activeView === 'radar' && <RadarView />}
        {activeView === 'command' && <CommandView />}
        {activeView === 'trading' && <TradingView />}
        {activeView === 'backtest' && <BacktestView />}
        {activeView === 'predict' && <PredictView symbol={symbol} />}
        {activeView === 'data' && <DataHubView />}
      </main>
    </div>
  )
}

