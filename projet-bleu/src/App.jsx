import React, { useState, useEffect } from 'react';
import {
  PlusCircle, Database, Trash2, RefreshCw, Loader2, Zap, Clock, CheckCircle2
} from 'lucide-react';

const API_BASE_URL = '/api';

const ProjetBleuApp = () => {
  const [view, setView] = useState('input');
  const [loading, setLoading] = useState(false);
  
  const [gatewaysCatalog, setGatewaysCatalog] = useState([]);
  const [edgesCatalog, setEdgesCatalog] = useState([]);
  const [orchestratorsCatalog, setOrchestratorsCatalog] = useState([]);
  const [productsCatalog, setProductsCatalog] = useState([]);

  const [inventory, setInventory] = useState(() => {
    const saved = localStorage.getItem('parcBleu');
    if (saved) {
        // Force la mise à jour des noms pour les anciens parcs sauvegardés
        return JSON.parse(saved).map(item => {
            if (item.type === 'Gateway') return { ...item, model: 'Gateway' };
            if (item.type === 'VCO') return { ...item, model: 'Orchestrator' };
            return item;
        });
    }
    return [
      { id: 1, type: 'Edge', model: 'Edge 500-N', qty: 80, version: '4.2.2' },
      { id: 2, type: 'Edge', model: 'Edge 510 Wi-Fi', qty: 10, version: '5.0.0' },
      { id: 3, type: 'Gateway', model: 'Gateway', qty: 4, version: '5.0.1' },
      { id: 4, type: 'VCO', model: 'Orchestrator', qty: 1, version: '5.2.3' }
    ];
  });

  useEffect(() => {
    localStorage.setItem('parcBleu', JSON.stringify(inventory));
  }, [inventory]);

  useEffect(() => {
    const fetchCatalogData = async () => {
      try {
        const [gatewaysRes, edgesRes, orchestratorsRes, productsRes] = await Promise.all([
          fetch(`${API_BASE_URL}/gateways`),
          fetch(`${API_BASE_URL}/edges`),
          fetch(`${API_BASE_URL}/orchestrators`),
          fetch(`${API_BASE_URL}/products`)
        ]);
        setGatewaysCatalog(await gatewaysRes.json());
        setEdgesCatalog(await edgesRes.json());
        setOrchestratorsCatalog(await orchestratorsRes.json());
        setProductsCatalog(await productsRes.json());
      } catch (err) {
        console.error("Erreur API:", err);
      }
    };
    fetchCatalogData();
  }, []);

  const parseDate = (dStr) => {
    if (!dStr || dStr === "null" || dStr === "None") return null;
    if (typeof dStr === 'string' && dStr.includes('/')) {
      const [d, m, y] = dStr.split('/');
      return new Date(y, m - 1, d);
    }
    const d = new Date(dStr);
    return isNaN(d.getTime()) ? null : d;
  };

  const analyzeItem = (item) => {
    const today = new Date('2026-02-07'); 
    const limitDate = new Date('2026-02-07');
    limitDate.setFullYear(limitDate.getFullYear() + 2);

    const productMatch = productsCatalog.find(p => p.model_name?.toLowerCase().trim() === item.model?.toLowerCase().trim());
    
    if (productMatch) {
      const pEolDate = parseDate(productMatch.end_of_life_date);
      const pEosDate = parseDate(productMatch.end_of_support_date);
      const alternativesList = productMatch.alternatives && Array.isArray(productMatch.alternatives) 
        ? productMatch.alternatives.join(', ') 
        : null;

      if (productMatch.is_end_of_life === true || 
         (pEolDate && pEolDate <= limitDate) || 
         (pEosDate && pEosDate <= limitDate)) {
        
        const isAlreadyPassed = (pEolDate && pEolDate < today) || (pEosDate && pEosDate < today) || productMatch.is_end_of_life === true;

        return { 
          status: isAlreadyPassed ? 'CRITICAL' : 'UPCOMING', 
          date: productMatch.end_of_life_date || productMatch.end_of_support_date, 
          alternatives: alternativesList
        };
      }
    }

    let softCatalog = [];
    if (item.type === 'Gateway') softCatalog = gatewaysCatalog;
    else if (item.type === 'Edge') softCatalog = edgesCatalog;
    else if (item.type === 'VCO') softCatalog = orchestratorsCatalog;
    
    const softMatch = softCatalog.find(c => {
      const apiVer = (c.version || "").toLowerCase().trim();
      const invVer = (item.version || "").toLowerCase().trim();
      if (!apiVer || !invVer) return false;
      if (apiVer === invVer) return true;
      if (apiVer.endsWith('.x')) return invVer.startsWith(apiVer.slice(0, -1));
      return false;
    });

    if (!softMatch) return { status: 'OK', date: null, alternatives: null };

    const sDateStr = softMatch.end_of_life_date || softMatch.end_of_support_date;
    const sDate = parseDate(sDateStr);

    if (softMatch.is_end_of_life === true || (sDate && sDate < today)) {
      return { status: 'CRITICAL', date: sDateStr || "Atteinte", alternatives: null };
    }

    if (sDate && sDate <= limitDate) {
      return { status: 'UPCOMING', date: sDateStr, alternatives: null };
    }

    return { status: 'OK', date: sDateStr, alternatives: null };
  };

  const runAnalysis = async () => {
    setLoading(true);
    setTimeout(() => {
      setView('dashboard');
      setLoading(false);
    }, 600);
  };

  const updateRow = (id, field, value) => {
    setInventory(inventory.map(item => item.id === id ? { ...item, [field]: value } : item));
  };

  const handleTypeChange = (id, newType) => {
    let newModel = '';
    if (newType === 'Gateway') newModel = 'Gateway';
    else if (newType === 'VCO') newModel = 'Orchestrator';
    else if (newType === 'Edge') newModel = '';
    
    setInventory(inventory.map(item => 
      item.id === id ? { ...item, type: newType, model: newModel } : item
    ));
  };

  const upcomingItems = inventory.filter(item => analyzeItem(item).status === 'UPCOMING');
  const criticalItems = inventory.filter(item => analyzeItem(item).status === 'CRITICAL');

  return (
    <div className="bg-gray-50 min-h-screen text-slate-900 font-sans">
      <nav className="bg-white border-b-4 border-blue-600 p-4 flex justify-between items-center shadow-md">
        <div className="flex items-center gap-4">
          <img src="/logoBleu.png" alt="Logo" className="h-16 w-16 object-contain" />
          <h1 className="text-3xl font-black uppercase italic tracking-tighter leading-none">Projet <span className="text-blue-600">Bleu</span></h1>
        </div>
        <div className="bg-black text-white px-3 py-1 text-[10px] font-bold uppercase tracking-widest leading-none">Orange 2026</div>
      </nav>

      <main className="p-8 max-w-5xl mx-auto">
        {view === 'input' ? (
          <section className="bg-white p-8 shadow-xl border border-gray-200 animate-in fade-in duration-500">
            <div className="flex justify-between items-center mb-8 border-b pb-4">
              <h2 className="text-2xl font-black uppercase italic flex items-center gap-2"><Database className="text-blue-600" /> Saisie du Parc Client</h2>
              <button onClick={() => setInventory([...inventory, { id: Date.now(), type: 'Edge', model: '', qty: 0, version: '' }])} className="bg-black text-white px-4 py-2 text-xs font-bold hover:bg-blue-600 transition-colors">
                + AJOUTER LIGNE
              </button>
            </div>

            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b-2 border-black text-[10px] uppercase font-black text-gray-400">
                  <th className="pb-4">Type</th>
                  <th className="pb-4">Modèle Hardware</th>
                  <th className="pb-4 text-center">Qté</th>
                  <th className="pb-4 text-center">Version Software</th>
                  <th className="pb-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {inventory.map((item) => (
                  <tr key={item.id} className="border-b border-gray-100 hover:bg-gray-50 transition-colors">
                    <td className="py-4">
                      <select 
                        className="bg-white border p-2 text-xs font-bold uppercase outline-none focus:border-blue-600 w-32" 
                        value={item.type} 
                        onChange={(e) => handleTypeChange(item.id, e.target.value)}
                      >
                        <option value="Edge">Edge</option>
                        <option value="Gateway">Gateway</option>
                        <option value="VCO">VCO</option>
                      </select>
                    </td>
                    <td className="py-4">
                      {item.type === 'Edge' ? (
                        <>
                          <input 
                            list={`models-${item.id}`}
                            className="bg-white border p-2 text-sm w-full outline-none focus:border-blue-600 font-medium" 
                            placeholder="Choisir modèle Edge..." 
                            value={item.model} 
                            onChange={(e) => updateRow(item.id, 'model', e.target.value)} 
                          />
                          <datalist id={`models-${item.id}`}>
                            {productsCatalog
                              .filter(p => p.model_name?.toLowerCase().startsWith('edge'))
                              .map((p, idx) => (
                                <option key={idx} value={p.model_name} />
                              ))
                            }
                          </datalist>
                        </>
                      ) : (
                        <input 
                          readOnly 
                          className="bg-gray-100 border p-2 text-sm w-full cursor-not-allowed font-black uppercase text-gray-500" 
                          value={item.model} 
                        />
                      )}
                    </td>
                    <td className="py-4 text-center">
                      <input type="number" className="border p-2 text-sm w-20 text-center outline-none focus:border-blue-600" value={item.qty} onChange={(e) => updateRow(item.id, 'qty', +e.target.value || 0)} />
                    </td>
                    <td className="py-4 text-center">
                      <input className="border p-2 text-sm w-40 text-center font-mono focus:border-blue-600" placeholder="ex: 2.8.2" value={item.version} onChange={(e) => updateRow(item.id, 'version', e.target.value)} />
                    </td>
                    <td className="py-4 text-right">
                      <button onClick={() => setInventory(inventory.filter(i => i.id !== item.id))} className="text-gray-300 hover:text-red-500 transition-colors"><Trash2 size={18} /></button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <div className="mt-10 flex justify-end">
              <button disabled={loading} onClick={runAnalysis} className="bg-blue-600 text-white px-10 py-4 font-black uppercase flex items-center gap-3 shadow-xl hover:bg-black transition-all">
                {loading ? <Loader2 className="animate-spin" /> : <><Zap size={20} /> Lancer l'Analyse</>}
              </button>
            </div>
          </section>
        ) : (
          <div className="space-y-8 animate-in slide-in-from-bottom-4 duration-500">
            <header className="flex justify-between items-end border-b-8 border-blue-600 pb-4">
               <h2 className="text-5xl font-black uppercase tracking-tighter italic leading-none">Audit <span className="text-blue-600">Technique</span></h2>
               <button onClick={() => setView('input')} className="text-[10px] font-black uppercase bg-black text-white px-4 py-2 hover:bg-blue-600 transition-colors">Retour Saisie</button>
            </header>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              <div className="bg-white p-6 shadow-xl border-t-8 border-orange-500">
                <h3 className="text-lg font-black uppercase mb-6 flex items-center gap-2 text-orange-600 font-black italic"><RefreshCw /> Phase 1 : Actions Immédiates</h3>
                
                <div className="space-y-6">
                  <div>
                    <p className="text-[10px] font-black uppercase text-orange-600 mb-3 tracking-widest border-b border-orange-100 pb-1 italic">Anticipation (Support &le; 2 ans)</p>
                    <div className="space-y-5">
                      {upcomingItems.length > 0 ? upcomingItems.map(item => {
                        const result = analyzeItem(item);
                        return (
                          <div key={item.id} className="p-3 bg-orange-50 border-l-4 border-orange-500 text-orange-900 rounded shadow-sm">
                            <p className="text-xs font-black uppercase">{item.qty} x {item.type} {item.model} ({item.version})</p>
                            <p className="text-[11px] mt-1">EOL Détectée : <span className="font-mono font-bold text-orange-700">{result.date}</span></p>
                            {result.alternatives && (
                              <p className="text-[11px] mt-1 font-medium italic">alternatives proposées : <span className="font-black text-orange-800 uppercase underline decoration-orange-300">{result.alternatives}</span></p>
                            )}
                          </div>
                        );
                      }) : <p className="text-xs text-gray-400 italic">Aucune alerte préventive.</p>}
                    </div>
                  </div>

                  <div>
                    <p className="text-[10px] font-black uppercase text-red-500 mb-3 tracking-widest border-b border-red-100 pb-1 italic">Urgences critiques (EOL Atteint)</p>
                    <div className="space-y-5">
                      {criticalItems.length > 0 ? criticalItems.map(item => {
                        const result = analyzeItem(item);
                        return (
                          <div key={item.id} className="p-3 bg-red-600 text-white rounded shadow-md flex justify-between items-center animate-in zoom-in-95">
                            <div>
                                <p className="text-xs font-black uppercase">{item.qty} x {item.type} {item.model} ({item.version})</p>
                                <p className="text-[11px] mt-1 opacity-90 font-medium">EOL Détectée : <span className="font-mono font-bold">{result.date}</span></p>
                                {result.alternatives && (
                                  <p className="text-[11px] mt-1 font-medium">alternatives proposées : <span className="font-black uppercase bg-black/20 px-1 rounded">{result.alternatives}</span></p>
                                )}
                            </div>
                            <span className="text-[8px] font-black uppercase bg-white text-red-600 px-2 py-1 rounded">Remplacement</span>
                          </div>
                        );
                      }) : <p className="text-xs text-gray-400 italic">Aucun équipement critique.</p>}
                    </div>
                  </div>
                </div>
              </div>

              <div className="bg-white p-6 shadow-xl border-t-8 border-blue-600">
                <h3 className="text-lg font-black uppercase mb-6 flex items-center gap-2 text-blue-600 font-black italic"><CheckCircle2 /> Phase 2 : Migration Planifiée</h3>
                <div className="space-y-4 font-bold text-[10px] uppercase">
                   <div className="p-4 bg-blue-50 border-l-4 border-blue-600 text-blue-800 leading-tight italic tracking-tighter mb-4">
                      Modernisation globale du parc et alignement sur les standards technologiques Orange 2026.
                   </div>
                   <div className="space-y-2">
                      <p className="flex justify-between border-b pb-1"><span>Inventaire Conforme</span><span className="text-blue-600">Gamme 7x0 / Cloud</span></p>
                      <p className="flex justify-between border-b pb-1"><span>Standard Software</span><span className="text-blue-600">LTS Stable v5.x</span></p>
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