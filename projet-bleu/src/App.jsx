import React, { useState, useEffect } from 'react';
import {
  PlusCircle, Database, Trash2, RefreshCw, Loader2, Zap, Clock, CheckCircle2, Milestone, Cpu, ShieldAlert
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
        return JSON.parse(saved).map(item => {
            if (item.type === 'Gateway') return { ...item, model: 'Gateway' };
            if (item.type === 'VCO') return { ...item, model: 'Orchestrator' };
            return item;
        });
    }
    return [
      { id: 1, type: 'Edge', model: 'Edge 500-N', qty: 80, version: '4.2.2' },
      { id: 2, type: 'Edge', model: '680', qty: 10, version: '5.0.0' },
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
    limitDate.setFullYear(limitDate.getFullYear() + 2); // Horizon 2 ans (2028)

    // --- ANALYSE HARDWARE (Phase 2) ---
    const productMatch = productsCatalog.find(p => p.model_name?.toLowerCase().trim() === item.model?.toLowerCase().trim());
    let hw = { status: 'OK', date: null, alternatives: null };
    
    if (productMatch) {
      const pEolDate = parseDate(productMatch.end_of_life_date);
      const pEosDate = parseDate(productMatch.end_of_support_date);
      const alternativesList = productMatch.alternatives && Array.isArray(productMatch.alternatives) 
        ? productMatch.alternatives.join(', ') 
        : null;

      const isPassed = productMatch.is_end_of_life === true || (pEolDate && pEolDate < today) || (pEosDate && pEosDate < today);
      const isSoon = (pEolDate && pEolDate <= limitDate) || (pEosDate && pEosDate <= limitDate);

      if (isPassed) hw = { status: 'CRITICAL', date: productMatch.end_of_life_date || productMatch.end_of_support_date, alternatives: alternativesList };
      else if (isSoon) hw = { status: 'UPCOMING', date: productMatch.end_of_life_date || productMatch.end_of_support_date, alternatives: alternativesList };
    }

    // --- ANALYSE SOFTWARE (Phase 1) ---
    let softCatalog = item.type === 'Gateway' ? gatewaysCatalog : (item.type === 'Edge' ? edgesCatalog : orchestratorsCatalog);
    const softMatch = softCatalog.find(c => {
      const apiVer = (c.version || "").toLowerCase().trim();
      const invVer = (item.version || "").toLowerCase().trim();
      return apiVer === invVer || (apiVer.endsWith('.x') && invVer.startsWith(apiVer.slice(0, -1)));
    });

    let sw = { status: 'OK', date: null };
    if (softMatch) {
      const sDateStr = softMatch.end_of_life_date || softMatch.end_of_support_date;
      const sDate = parseDate(sDateStr);
      const isPassed = softMatch.is_end_of_life === true || (sDate && sDate < today);
      const isSoon = sDate && sDate <= limitDate;

      if (isPassed) sw = { status: 'CRITICAL', date: sDateStr || "Atteinte" };
      else if (isSoon) sw = { status: 'UPCOMING', date: sDateStr };
    }

    return { hw, sw };
  };

  const runAnalysis = async () => {
    setLoading(true);
    const filteredVersions = inventory
      .filter(item => analyzeItem(item).hw.status !== 'CRITICAL')
      .map(item => ({
        component: `${item.type} ${item.model}`,
        current_version: item.version,
        target_version: "6.4.1"
      }));

    try {
      await fetch(`${API_BASE_URL}/analyze_upgrade_path`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ versions: filteredVersions })
      });
      setView('dashboard');
    } catch (error) {
      setView('dashboard');
    } finally {
      setLoading(false);
    }
  };

  const updateRow = (id, field, value) => {
    setInventory(inventory.map(item => item.id === id ? { ...item, [field]: value } : item));
  };

  const handleTypeChange = (id, newType) => {
    let newModel = '';
    if (newType === 'Gateway') newModel = 'Gateway';
    else if (newType === 'VCO') newModel = 'Orchestrator';
    else if (newType === 'Edge') newModel = '';
    setInventory(inventory.map(item => item.id === id ? { ...item, type: newType, model: newModel } : item));
  };

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
              <button onClick={() => setInventory([...inventory, { id: Date.now(), type: 'Edge', model: '', qty: 0, version: '' }])} className="bg-black text-white px-4 py-2 text-xs font-bold hover:bg-blue-600 transition-colors shadow-sm">
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
                      <select className="bg-white border p-2 text-xs font-bold uppercase outline-none focus:border-blue-600 w-32" value={item.type} onChange={(e) => handleTypeChange(item.id, e.target.value)}>
                        <option value="Edge">Edge</option>
                        <option value="Gateway">Gateway</option>
                        <option value="VCO">VCO</option>
                      </select>
                    </td>
                    <td className="py-4">
                      {item.type === 'Edge' ? (
                        <>
                          <input list={`models-${item.id}`} className="bg-white border p-2 text-sm w-full outline-none focus:border-blue-600 font-medium" placeholder="Modèle Edge..." value={item.model} onChange={(e) => updateRow(item.id, 'model', e.target.value)} />
                          <datalist id={`models-${item.id}`}>
                            {productsCatalog.filter(p => p.model_name?.toLowerCase().startsWith('edge')).map((p, idx) => (<option key={idx} value={p.model_name} />))}
                          </datalist>
                        </>
                      ) : (
                        <input readOnly className="bg-gray-100 border p-2 text-sm w-full cursor-not-allowed font-black uppercase text-gray-500" value={item.model} />
                      )}
                    </td>
                    <td className="py-4 text-center"><input type="number" className="border p-2 text-sm w-20 text-center outline-none" value={item.qty} onChange={(e) => updateRow(item.id, 'qty', +e.target.value || 0)} /></td>
                    <td className="py-4 text-center"><input className="border p-2 text-sm w-40 text-center font-mono" placeholder="ex: 2.8.2" value={item.version} onChange={(e) => updateRow(item.id, 'version', e.target.value)} /></td>
                    <td className="py-4 text-right"><button onClick={() => setInventory(inventory.filter(i => i.id !== item.id))} className="text-gray-300 hover:text-red-500 transition-colors"><Trash2 size={18} /></button></td>
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
               <h2 className="text-5xl font-black uppercase tracking-tighter italic">Audit <span className="text-blue-600">Technique</span></h2>
               <button onClick={() => setView('input')} className="text-[10px] font-black uppercase bg-black text-white px-4 py-2 hover:bg-blue-600 transition-colors">Retour Saisie</button>
            </header>

            {/* PHASE 0 : TRAJECTOIRE */}
            <div className="bg-black text-white p-6 shadow-xl border-l-8 border-blue-600">
                <h3 className="text-lg font-black uppercase mb-2 flex items-center gap-2 italic"><Milestone className="text-blue-400" /> Trajectoire Software Cible</h3>
                <p className="text-sm font-bold tracking-tight">c'est ce super chemin pour la dernière version : <span className="text-blue-400 font-mono">/test/coucou</span></p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              {/* PHASE 1 : LOGICIEL (SOFTWARE) - Regroupe toutes les versions périmées ou à moins de 2 ans */}
              <div className="bg-white p-6 shadow-xl border-t-8 border-orange-500">
                <h3 className="text-lg font-black uppercase mb-6 flex items-center gap-2 text-orange-600 italic font-black"><RefreshCw /> Phase 1 : Cycle de vie Software</h3>
                <div className="space-y-6">
                  {inventory.map(item => {
                    const { sw } = analyzeItem(item);
                    if (sw.status === 'OK') return null;
                    return (
                      <div key={item.id} className={`p-3 border-l-4 rounded shadow-sm ${sw.status === 'CRITICAL' ? 'bg-red-50 border-red-500' : 'bg-orange-50 border-orange-500'}`}>
                        <p className="text-xs font-black uppercase">{item.qty} x {item.type} {item.model} ({item.version})</p>
                        <p className="text-[11px] mt-1 font-semibold">EOL Détectée : <span className="font-mono">{sw.date}</span></p>
                        <p className={`text-[9px] mt-1 font-bold uppercase ${sw.status === 'CRITICAL' ? 'text-red-600' : 'text-orange-600'}`}>
                          {sw.status === 'CRITICAL' ? '⚠️ Version obsolète : Mise à jour immédiate' : 'ℹ️ Fin de support proche : Mise à jour planifiée'}
                        </p>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* PHASE 2 : MATÉRIEL (HARDWARE) - Regroupe tous les boîtiers périmés ou à moins de 2 ans */}
              <div className="bg-white p-6 shadow-xl border-t-8 border-blue-600">
                <h3 className="text-lg font-black uppercase mb-6 flex items-center gap-2 text-blue-600 italic font-black"><Cpu /> Phase 2 : Obsolescence Hardware</h3>
                <div className="space-y-6">
                  {inventory.map(item => {
                    const { hw } = analyzeItem(item);
                    if (hw.status === 'OK') return null;
                    return (
                      <div key={item.id} className={`p-3 border-l-4 rounded shadow-md ${hw.status === 'CRITICAL' ? 'bg-red-600 text-white' : 'bg-orange-50 border-orange-500 text-orange-900'}`}>
                        <p className="text-xs font-black uppercase tracking-tight">{item.qty} x {item.type} {item.model} ({item.version})</p>
                        <p className="text-[11px] mt-1 font-medium italic">EOL Détectée : <span className="font-mono font-bold underline decoration-dotted">{hw.date}</span></p>
                        {hw.alternatives && (
                          <p className={`text-[11px] mt-1 font-medium ${hw.status === 'CRITICAL' ? 'text-white' : 'text-orange-800'}`}>
                            alternatives proposées : <span className={`font-black uppercase ${hw.status === 'CRITICAL' ? 'bg-black/20' : 'bg-orange-200'} px-1 rounded`}>{hw.alternatives}</span>
                          </p>
                        )}
                      </div>
                    );
                  })}
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