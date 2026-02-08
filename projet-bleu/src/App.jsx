import React, { useState, useEffect } from 'react';
import {
  PlusCircle, Database, Trash2, RefreshCw, Loader2, Zap, Clock, CheckCircle2, Milestone, Cpu, ShieldAlert, ArrowRight
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';

const API_BASE_URL = 'https://bleu.clementpickel.fr/api';

const ProjetBleuApp = () => {
  const [view, setView] = useState('input');
  const [loading, setLoading] = useState(false);
  const [processingPdfs, setProcessingPdfs] = useState(false);
  const [upgradeAnalysis, setUpgradeAnalysis] = useState('');
  
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

  const processPdfs = async () => {
    setProcessingPdfs(true);
    try {
      const response = await fetch(`${API_BASE_URL}/process`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      
      if (response.ok) {
        const data = await response.json();
        console.log('PDFs processed:', data);
        // Reload catalog data after processing
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
      }
    } catch (error) {
      console.error('Error processing PDFs:', error);
    } finally {
      setProcessingPdfs(false);
    }
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
    
    // Group inventory by component type and get representative versions
    const getComponentVersion = (type) => {
      const items = inventory.filter(item => item.type === type);
      // Get the most common or first version for each component type
      return items.length > 0 ? items[0].version : null;
    };

    const versions = [];
    const orchestratorVersion = getComponentVersion('VCO');
    const gatewayVersion = getComponentVersion('Gateway');
    const edgeVersion = getComponentVersion('Edge');

    if (orchestratorVersion) versions.push({ component: 'orchestrator', current_version: orchestratorVersion });
    if (gatewayVersion) versions.push({ component: 'gateway', current_version: gatewayVersion });
    if (edgeVersion) versions.push({ component: 'edge', current_version: edgeVersion });

    try {
      const response = await fetch(`${API_BASE_URL}/analyze-upgrade-with-pdfs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ versions })
      });
      
      const data = await response.json();
      console.log('Analysis response:', data);
      
      // Extract text from response - prioritize reasoning field
      let analysisText = '';
      if (typeof data === 'string') {
        analysisText = data;
      } else if (data.result && data.result.reasoning) {
        analysisText = typeof data.result.reasoning === 'string' ? data.result.reasoning : JSON.stringify(data.result.reasoning);
      }
      
      setUpgradeAnalysis(analysisText);
      setView('dashboard');
    } catch (error) {
      console.error('Error analyzing upgrade:', error);
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
          <button 
            onClick={processPdfs} 
            disabled={processingPdfs}
            className="bg-blue-600 text-white px-3 py-2 text-xs font-bold hover:bg-blue-700 disabled:bg-gray-400 transition-colors shadow-sm rounded flex items-center gap-2"
          >
            {processingPdfs ? (
              <>
                <Loader2 size={14} className="animate-spin" />
                Processing...
              </>
            ) : (
              <>
                <Database size={14} />
                Process PDFs
              </>
            )}
          </button>
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

            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                {/* PHASE 1 : LOGICIEL (SOFTWARE) - Local analysis */}
                <div className="bg-white p-6 shadow-xl border-t-8 border-orange-500">
                  <h3 className="text-lg font-black uppercase mb-6 flex items-center gap-2 text-orange-600 italic"><RefreshCw /> Phase 1 : Cycle de vie Software</h3>
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

                {/* PHASE 2 : MATÉRIEL (HARDWARE) - Local analysis */}
                <div className="bg-white p-6 shadow-xl border-t-8 border-blue-600">
                  <h3 className="text-lg font-black uppercase mb-6 flex items-center gap-2 text-blue-600 italic"><Cpu /> Phase 2 : Obsolescence Hardware</h3>
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
        
{/* TRAJECTOIRE D'UPGRADE OPTIMALE */}
{upgradeAnalysis && (
  <div className="bg-white shadow-2xl border-l-[12px] border-blue-600 rounded-r-2xl mb-20 overflow-hidden animate-in fade-in slide-in-from-left-6 duration-1000">
    {/* Header Premium */}
    <div className="bg-gradient-to-r from-slate-900 to-slate-800 px-8 py-5 flex items-center justify-between border-b border-white/10">
      <div className="flex items-center gap-4">
        <div className="bg-blue-600 p-2 rounded-lg shadow-lg shadow-blue-900/20">
          <Milestone className="text-white" size={24} />
        </div>
        <div>
          <h3 className="text-white font-black uppercase tracking-widest text-sm">Plan de Migration Automatisé</h3>
          <p className="text-blue-400 text-[10px] font-bold uppercase tracking-tighter">Chemins de mise à jour optimisés via intelligence documentaire</p>
        </div>
      </div>
    </div>

    {/* Zone de contenu stylisée */}
    <div className="p-8 bg-slate-50/50">
      <ReactMarkdown
        components={{
          // On customise le rendu des paragraphes
          p: ({ children }) => <p className="text-slate-700 font-bold mb-6 text-sm leading-relaxed">{children}</p>,
          // On transforme les listes en flux d'étapes
          ul: ({ children }) => <ul className="space-y-4 relative">{children}</ul>,
          // Chaque ligne (li) devient une carte d'étape
          li: ({ children }) => (
            <li className="group flex items-start gap-4 bg-white p-4 rounded-xl border border-slate-200 shadow-sm hover:shadow-md hover:border-blue-300 transition-all duration-300 transform hover:-translate-x-1">
              <div className="mt-1 bg-blue-100 text-blue-600 p-1.5 rounded-lg group-hover:bg-blue-600 group-hover:text-white transition-colors">
                <ArrowRight size={14} className="font-bold" />
              </div>
              <div className="text-slate-600 font-bold text-sm tracking-tight leading-snug">
                {children}
              </div>
            </li>
          ),
          // Style pour le gras
          strong: ({ children }) => <strong className="text-blue-600 font-black tracking-tight">{children}</strong>,
          // Style pour les titres éventuels dans le markdown
          h3: ({ children }) => <h4 className="text-slate-900 font-black uppercase text-xs mb-3 flex items-center gap-2 italic">{children}</h4>
        }}
      >
        {upgradeAnalysis}
      </ReactMarkdown>
    </div>
  </div>
)}
      </main>
    </div>
  );
};

export default ProjetBleuApp;