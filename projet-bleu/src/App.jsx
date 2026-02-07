import React, { useState, useEffect } from 'react';
import { PlusCircle, Database, Trash2, ArrowRight, AlertCircle, CheckCircle2, RefreshCw, BarChart3 } from 'lucide-react';

const ProjetBleuApp = () => {
  const [view, setView] = useState('input');
  
  // 1. Initialisation : On regarde d'abord dans le localStorage
  const [inventory, setInventory] = useState(() => {
    const saved = localStorage.getItem('parcBleu');
    if (saved) return JSON.parse(saved);
    
    // Valeurs par défaut du cas client si rien n'est stocké [cite: 62, 63, 64, 65]
    return [
      { id: 1, type: 'Edge', model: '840', qty: 80, version: '4.2.2' },
      { id: 2, type: 'Edge', model: '680', qty: 10, version: '5.0.0' },
      { id: 3, type: 'Gateway', model: 'VNF', qty: 4, version: '5.0.1' },
      { id: 4, type: 'VCO', model: 'VECO', qty: 1, version: '5.2.3' }
    ];
  });

  // 2. Sauvegarde automatique à chaque changement de l'inventaire
  useEffect(() => {
    localStorage.setItem('parcBleu', JSON.stringify(inventory));
  }, [inventory]);

  const addRow = () => {
    const newId = Date.now();
    setInventory([...inventory, { id: newId, type: 'Edge', model: '', qty: 0, version: '' }]);
  };

  const updateRow = (id, field, value) => {
    setInventory(inventory.map(item => item.id === id ? { ...item, [field]: value } : item));
  };

  const deleteRow = (id) => setInventory(inventory.filter(item => item.id !== id));
  const hasErrors = inventory.some(item => item.qty <= 0 || item.version.trim() === "" || item.model.trim() === "");

  return (
    <div className="bg-gray-50 min-h-screen text-slate-900 font-sans">
      <nav className="bg-white border-b-4 border-blue-600 p-4 flex justify-between items-center shadow-md">
        <div className="flex items-center gap-4">
          <img src="/logoBleu.png" alt="Logo Projet Bleu" className="h-16 w-16 object-contain" />
          <h1 className="text-3xl font-black uppercase tracking-tighter italic leading-none">
            Hackaton <span className="text-blue-600">Orange</span>
          </h1>
        </div>
        <div className="flex gap-2 text-xs font-bold uppercase">
          <button onClick={() => setView('input')} className={`px-4 py-2 border ${view === 'input' ? 'bg-blue-600 text-white' : 'bg-white text-blue-600 border-blue-600'}`}>Saisie Inventaire</button>
          <button onClick={() => !hasErrors && setView('dashboard')} className={`px-4 py-2 border ${view === 'dashboard' ? 'bg-blue-600 text-white' : 'bg-white text-blue-600 border-blue-600'} ${hasErrors ? 'opacity-50 cursor-not-allowed' : ''}`}>Dashboard Analyse</button>
        </div>
      </nav>

      <main className="p-8 max-w-6xl mx-auto">
        {view === 'input' ? (
          <section className="bg-white p-8 shadow-xl border border-gray-200 animate-in fade-in duration-500">
            <div className="flex justify-between items-center mb-8">
              <h2 className="text-2xl font-black uppercase flex items-center gap-2">
                <Database className="text-blue-600" /> Parc Client Actuel
              </h2>
              <button onClick={addRow} className="bg-black text-white px-4 py-2 text-xs font-bold hover:bg-blue-600 transition-colors flex items-center gap-2">
                <PlusCircle size={16} /> AJOUTER UNE LIGNE
              </button>
            </div>

            {hasErrors && (
              <div className="mb-6 p-4 bg-red-100 border-l-4 border-red-500 text-red-700 text-sm flex items-center gap-2 font-bold">
                <AlertCircle size={18} />
                <span>Données incomplètes pour l'audit.</span>
              </div>
            )}

            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b-2 border-black text-xs uppercase font-black text-gray-400">
                  <th className="pb-4">Type</th>
                  <th className="pb-4">Modèle Hardware</th>
                  <th className="pb-4">Quantité</th>
                  <th className="pb-4">Version SW</th>
                  <th className="pb-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {inventory.map((item) => (
                  <tr key={item.id} className="border-b border-gray-100 group hover:bg-gray-50 transition-colors">
                    <td className="py-4">
                      <select className="bg-white border p-2 text-sm font-bold outline-none focus:ring-2 focus:ring-blue-600" value={item.type} onChange={(e) => updateRow(item.id, 'type', e.target.value)}>
                        <option>Edge</option>
                        <option>Gateway</option>
                        <option>VCO</option>
                      </select>
                    </td>
                    <td className="py-4">
                      <input type="text" className="bg-white border p-2 text-sm outline-none focus:ring-2 focus:ring-blue-600" value={item.model} onChange={(e) => updateRow(item.id, 'model', e.target.value)} />
                    </td>
                    <td className="py-4">
                      <input type="number" className="bg-white border p-2 text-sm w-24" value={item.qty} onChange={(e) => updateRow(item.id, 'qty', parseInt(e.target.value) || 0)} />
                    </td>
                    <td className="py-4">
                      <input type="text" className="bg-white border p-2 text-sm" value={item.version} onChange={(e) => updateRow(item.id, 'version', e.target.value)} />
                    </td>
                    <td className="py-4 text-right">
                      <button onClick={() => deleteRow(item.id)} className="text-gray-300 hover:text-red-500"><Trash2 size={18} /></button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <div className="mt-10 flex justify-end">
              <button disabled={hasErrors} onClick={() => setView('dashboard')} className={`px-8 py-4 font-black uppercase flex items-center gap-3 transition-all ${hasErrors ? 'bg-gray-300 cursor-not-allowed text-gray-500' : 'bg-blue-600 text-white hover:bg-black'}`}>
                Générer Préconisations <ArrowRight />
              </button>
            </div>
          </section>
        ) : (
          /* SECTION DASHBOARD IDENTIQUE AU PRÉCÉDENT MAIS CONNECTÉE AUX DONNÉES LOCALES */
          <div className="space-y-8 animate-in slide-in-from-bottom-4 duration-500">
            <header className="flex justify-between items-end border-b-8 border-blue-600 pb-4">
               <div>
                  <h2 className="text-5xl font-black uppercase tracking-tighter">Audit <span className="text-blue-600">Technique</span></h2>
                  <p className="text-gray-500 font-bold uppercase text-xs mt-1 italic">Données synchronisées avec le stockage local</p>
               </div>
               <div className="text-right text-xs font-bold uppercase bg-black text-white p-2">
                  Plan de migration 2026
               </div>
            </header>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              <div className="bg-white p-6 shadow-xl border-t-8 border-orange-500">
                <h3 className="text-lg font-black uppercase mb-4 flex items-center gap-2"><RefreshCw className="text-orange-500" /> Phase 1 : Upgrade Software </h3>
                <div className="space-y-3">
                  {inventory.filter(i => i.version < "5.2.0").map(item => (
                    <div key={item.id} className="p-3 bg-orange-50 border-l-4 border-orange-500 text-sm">
                      <p className="font-bold uppercase text-xs">{item.model} ({item.qty} unités) </p>
                      <p className="text-orange-600 font-bold mt-1">Migration vers LTS nécessaire[cite: 50].</p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="bg-white p-6 shadow-xl border-t-8 border-blue-600">
                <h3 className="text-lg font-black uppercase mb-4 flex items-center gap-2"><CheckCircle2 className="text-blue-600" /> Phase 2 : Remplacement HW [cite: 80]</h3>
                <div className="space-y-4 text-sm">
                   <div className="p-3 bg-blue-50 border-l-4 border-blue-600 italic font-medium">
                      Analyse basée sur les notices End-of-Life HW[cite: 77].
                   </div>
                   {inventory.filter(i => i.model === '840').map(i => (
                     <p key={i.id} className="font-bold">➜ {i.qty} x Edge 840 à remplacer par Gamme 710/720[cite: 96, 97].</p>
                   ))}
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