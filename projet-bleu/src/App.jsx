import React, { useState, useEffect } from 'react';
import {
  PlusCircle, Database, Trash2, ArrowRight, AlertCircle, CheckCircle2, RefreshCw, BarChart3, Loader2, Zap, Clock
} from 'lucide-react';

const API_BASE_URL = '/api';

const ProjetBleuApp = () => {
  const [view, setView] = useState('input');
  const [loading, setLoading] = useState(false);
  
  const [gatewaysCatalog, setGatewaysCatalog] = useState([]);
  const [edgesCatalog, setEdgesCatalog] = useState([]);
  const [orchestratorsCatalog, setOrchestratorsCatalog] = useState([]);

  const [inventory, setInventory] = useState(() => {
    const saved = localStorage.getItem('parcBleu');
    if (saved) return JSON.parse(saved);
    return [
      { id: 1, type: 'Edge', model: '840', qty: 80, version: '4.2.2' },
      { id: 2, type: 'Edge', model: '680', qty: 10, version: '5.0.0' },
      { id: 3, type: 'Gateway', model: 'VNF', qty: 4, version: '5.0.1' },
      { id: 4, type: 'VCO', model: 'VECO', qty: 1, version: '5.2.3' }
    ];
  });

  useEffect(() => {
    localStorage.setItem('parcBleu', JSON.stringify(inventory));
  }, [inventory]);

  useEffect(() => {
    const fetchCatalogData = async () => {
      try {
        const [gatewaysRes, edgesRes, orchestratorsRes] = await Promise.all([
          fetch(`${API_BASE_URL}/gateways`),
          fetch(`${API_BASE_URL}/edges`),
          fetch(`${API_BASE_URL}/orchestrators`)
        ]);
        setGatewaysCatalog(await gatewaysRes.json());
        setEdgesCatalog(await edgesRes.json());
        setOrchestratorsCatalog(await orchestratorsRes.json());
      } catch (err) {
        console.error("Erreur API:", err);
      }
    };
    fetchCatalogData();
  }, []);

  // ANALYSE : Règles strictes Orange
  const analyzeItem = (item) => {
    let catalog = [];
    if (item.type === 'Gateway') catalog = gatewaysCatalog;
    else if (item.type === 'Edge') catalog = edgesCatalog;
    else if (item.type === 'VCO') catalog = orchestratorsCatalog;
    
    const match = catalog.find(c => {
      const apiVer = (c.version || "").toLowerCase().trim();
      const invVer = (item.version || "").toLowerCase().trim();
      if (!apiVer || !invVer) return false;
      if (apiVer === invVer) return true;
      if (apiVer.endsWith('.x')) return invVer.startsWith(apiVer.slice(0, -1));
      return false;
    });
    
    if (!match) return { status: 'OK', date: null };

    // Parseur de date robuste pour 28/02/2026 ou February 28, 2026
    const parseDate = (dStr) => {
      if (!dStr) return null;
      if (dStr.includes('/')) {
        const [d, m, y] = dStr.split('/');
        return new Date(y, m - 1, d);
      }
      return new Date(dStr);
    };

    const today = new Date('2026-02-07'); 
    const limitDate = new Date('2026-02-07');
    limitDate.setFullYear(limitDate.getFullYear() + 2); // Horizon 2028

    const eolDate = parseDate(match.end_of_life_date);

    // RÈGLE 1 : CRITIQUE (is_end_of_life True OU date dans le passé)
    if (match.is_end_of_life === true || (eolDate && eolDate < today)) {
      return { status: 'CRITICAL', date: match.end_of_life_date };
    }

    // RÈGLE 2 : ANTICIPATION (eol false MAIS date <= 2 ans)
    if (eolDate && eolDate <= limitDate) {
      return { status: 'UPCOMING', date: match.end_of_life_date };
    }

    return { status: 'OK', date: match.end_of_life_date };
  };

  const runAnalysis = async () => {
    setLoading(true);
    setTimeout(() => {
      setView('dashboard');
      setLoading(false);
    }, 800);
  };

  const updateRow = (id, field, value) => {
    setInventory(inventory.map(item => item.id === id ? { ...item, [field]: value } : item));
  };

  const deleteRow = (id) => setInventory(inventory.filter(item => item.id !== id));

  return (
    <div className="bg-gray-50 min-h-screen text-slate-900 font-sans">
      <nav className="bg-white border-b-4 border-blue-600 p-4 flex justify-between items-center shadow-md">
        <div className="flex items-center gap-4">
          <img src="/logoBleu.png" alt="Logo" className="h-16 w-16 object-contain" />
          <h1 className="text-3xl font-black uppercase italic tracking-tighter">Projet <span className="text-blue-600">Bleu</span></h1>
        </div>
        <div className="bg-black text-white px-3 py-1 text-[10px] font-bold uppercase">Orange Hackathon 2026</div>
      </nav>

      <main className="p-8 max-w-5xl mx-auto">
        {view === 'input' ? (
          <section className="bg-white p-8 shadow-xl border border-gray-200 animate-in fade-in duration-500">
            <div className="flex justify-between items-center mb-8 border-b pb-4 font-black italic text-2xl uppercase">
              <h2><Database className="inline text-blue-600 mr-2" /> Saisie du Parc</h2>
              <button onClick={() => setInventory([...inventory, { id: Date.now(), type: 'Edge', model: '', qty: 0, version: '' }])} className="bg-black text-white px-4 py-2 text-xs font-bold hover:bg-blue-600 transition-colors">
                + AJOUTER LIGNE
              </button>
            </div>

            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b-2 border-black text-[10px] uppercase font-black text-gray-400">
                  <th className="pb-4">Type</th>
                  <th className="pb-4">Modèle</th>
                  <th className="pb-4 text-center">Qté</th>
                  <th className="pb-4 text-center">Version Software</th>
                  <th className="pb-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {inventory.map((item) => (
                  <tr key={item.id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-4">
                      <select className="bg-white border p-2 text-xs font-bold uppercase outline-none focus:border-blue-600 w-32" value={item.type} onChange={(e) => updateRow(item.id, 'type', e.target.value)}>
                        <option value="Edge">Edge</option>
                        <option value="Gateway">Gateway</option>
                        <option value="VCO">VCO</option>
                      </select>
                    </td>
                    <td className="py-4"><input className="border p-2 text-sm w-full outline-none focus:border-blue-600 font-medium" value={item.model} onChange={(e) => updateRow(item.id, 'model', e.target.value)} /></td>
                    <td className="py-4 text-center"><input type="number" className="border p-2 text-sm w-20 text-center outline-none" value={item.qty} onChange={(e) => updateRow(item.id, 'qty', +e.target.value || 0)} /></td>
                    <td className="py-4 text-center"><input className="border p-2 text-sm w-40 text-center font-mono" placeholder="ex: 2.8.2" value={item.version} onChange={(e) => updateRow(item.id, 'version', e.target.value)} /></td>
                    <td className="py-4 text-right"><button onClick={() => deleteRow(item.id)} className="text-gray-300 hover:text-red-500"><Trash2 size={18} /></button></td>
                  </tr>
                ))}
              </tbody>
            </table>

            <div className="mt-10 flex justify-end">
              <button onClick={runAnalysis} className="bg-blue-600 text-white px-10 py-4 font-black uppercase flex items-center gap-3 shadow-xl hover:bg-black transition-all">
                {loading ? <Loader2 className="animate-spin" /> : <><Zap size={20} /> Lancer l'Audit</>}
              </button>
            </div>
          </section>
        ) : (
          <div className="space-y-8 animate-in slide-in-from-bottom-4 duration-500">
            <header className="flex justify-between items-end border-b-8 border-blue-600 pb-4">
               <h2 className="text-5xl font-black uppercase tracking-tighter italic">Résultats <span className="text-blue-600">Audit</span></h2>
               <button onClick={() => setView('input')} className="text-[10px] font-black uppercase bg-black text-white px-4 py-2">Retour Saisie</button>
            </header>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              <div className="bg-white p-6 shadow-xl border-t-8 border-orange-500">
                <h3 className="text-lg font-black uppercase mb-6 flex items-center gap-2 text-orange-600"><RefreshCw /> Phase 1 : Actions Immédiates</h3>
                
                <div className="space-y-6">
                  {/* CATEGORIE : ANTICIPATION (Format: 10 x Edge 680 (2.6.0)) */}
                  <div>
                    <p className="text-[10px] font-black uppercase text-orange-600 mb-3 tracking-widest border-b border-orange-100 pb-1 italic">Anticipation (Horizon 2 ans)</p>
                    <div className="space-y-3">
                      {inventory.filter(item => analyzeItem(item).status === 'UPCOMING').map(item => (
                        <div key={item.id} className="p-3 bg-orange-50 border-l-4 border-orange-500 text-orange-900 rounded flex justify-between items-center shadow-sm">
                          <div>
                            <p className="text-xs font-black uppercase">
                              {item.qty} x {item.type} {item.model} ({item.version})
                            </p>
                            <p className="text-[9px] font-bold opacity-80 uppercase italic font-mono text-orange-700">EOL : {analyzeItem(item).date}</p>
                          </div>
                          <span className="text-[8px] font-black uppercase bg-orange-200 px-2 py-1 rounded">À planifier</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* CATEGORIE : CRITIQUE (Format: 10 x Edge 680 (2.6.0)) */}
                  <div>
                    <p className="text-[10px] font-black uppercase text-red-500 mb-3 tracking-widest border-b border-red-100 pb-1">Urgences critiques (EOL Atteint)</p>
                    <div className="space-y-3">
                      {inventory.filter(item => analyzeItem(item).status === 'CRITICAL').map(item => (
                        <div key={item.id} className="p-3 bg-red-600 text-white rounded shadow-md flex justify-between items-center animate-in zoom-in-95">
                          <div>
                            <p className="text-xs font-black uppercase">
                              {item.qty} x {item.type} {item.model} ({item.version})
                            </p>
                            <p className="text-[9px] font-bold opacity-90 uppercase italic font-mono text-red-100">Statut : Obsolescence confirmée</p>
                          </div>
                          <span className="text-[8px] font-black uppercase bg-white text-red-600 px-2 py-1 rounded">Remplacement</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              <div className="bg-white p-6 shadow-xl border-t-8 border-blue-600">
                <h3 className="text-lg font-black uppercase mb-6 flex items-center gap-2 text-blue-600"><CheckCircle2 /> Phase 2 : Migration Planifiée</h3>
                <div className="space-y-4">
                   <div className="p-4 bg-blue-50 border-l-4 border-blue-600 text-[10px] text-blue-800 font-bold uppercase italic leading-tight">
                      Mise en conformité globale du parc pour Orange 2026.
                   </div>
                   <div className="space-y-2 text-[10px] font-black uppercase">
                      <p className="flex justify-between border-b pb-1"><span>Matériel Sain</span><span className="text-blue-600">Gamme 7x0</span></p>
                      <p className="flex justify-between border-b pb-1"><span>Software</span><span className="text-blue-600">LTS Stable v5.x</span></p>
                   </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
};

export default ProjetBleuApp;