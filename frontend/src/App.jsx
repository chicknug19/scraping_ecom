import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import './App.css';

export default function App() {
  // --- STATE UNTUK SCRAPING ---
  const [keyword, setKeyword] = useState('');
  const [limit, setLimit] = useState(10);
  const [location, setLocation] = useState(''); 
  const [loading, setLoading] = useState(false);
  const [scrapedData, setScrapedData] = useState([]);
  // State untuk Scraper Toko
  const [storeUsernames, setStoreUsernames] = useState("");
  const [storeLimit, setStoreLimit] = useState(10);
  const [storeTasks, setStoreTasks] = useState([
    { username: "", keyword: "", limit: 10, isAll: false }
  ]);
  const [isStoreLoading, setIsStoreLoading] = useState(false);
  const [showResults, setShowResults] = useState(true);

  // --- STATE UNTUK AI CHAT ---
  const [prompt, setPrompt] = useState('');
  const [aiLoading, setAiLoading] = useState(false);
  const [aiResponse, setAiResponse] = useState('');

  const handleScrape = async () => {
    if (!keyword) return alert("Masukkan keyword terlebih dahulu!");
    
    setLoading(true);
    setScrapedData([]);


    try {
      const response = await fetch('scraper-radi-caheg6c6g6gcghbf.indonesiacentral-01.azurewebsites.net', {
        // const response = await fetch('http://localhost:8000/api/scrape', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                keyword, 
                limit: parseInt(limit),
                location 
            })
        });
        
        const data = await response.json();
        if (data.results) {
            setScrapedData(data.results);
            alert(`Scraping selesai! Mendapatkan ${data.results.length} produk.`);
        }
    } catch (error) {
        console.error("Terjadi kesalahan:", error);
        alert("Gagal terhubung ke backend.");
    }
    setLoading(false);
  };

  // --- FUNGSI AI CHAT ---
  const handleTemplateClick = (templateText) => {
    setPrompt(templateText);
  };

  const handleChatAI = async () => {
    if (!prompt) return alert("Ketikkan instruksi untuk AI terlebih dahulu!");
    
    setAiLoading(true);
    setAiResponse(''); 

    try {
        const response = await fetch('scraper-radi-caheg6c6g6gcghbf.indonesiacentral-01.azurewebsites.net', {
        // const response = await fetch('http://localhost:8000/api/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_prompt: prompt })
        });
        
        const data = await response.json();
        if (data.ai_response) {
            setAiResponse(data.ai_response);
        } else if (data.error) {
            setAiResponse(`Error: ${data.error}`);
        }
    } catch (error) {
        console.error("Terjadi kesalahan AI:", error);
        setAiResponse("Gagal terhubung ke layanan AI.");
    }
    setAiLoading(false);
  };


  // FUNGSI MANAJEMEN FORM
  const addTask = () => setStoreTasks([...storeTasks, { username: "", keyword: "", limit: 10, isAll: false }]);
  
  const updateTask = (index, field, value) => {
    const newTasks = [...storeTasks];
    newTasks[index][field] = value;
    setStoreTasks(newTasks);
  };
  
  const removeTask = (index) => {
    const newTasks = storeTasks.filter((_, i) => i !== index);
    setStoreTasks(newTasks);
  };

  // FUNGSI SUBMIT KE BACKEND
  const handleStoreScrape = async () => {
    const validTasks = storeTasks.filter(t => t.username.trim() !== "");
    if (validTasks.length === 0) {
      alert("⚠️ Masukkan minimal 1 username toko!");
      return;
    }

    setIsStoreLoading(true);
    setScrapedData([]); // Bersihkan layar sebelum memuat yang baru
    
    try {
      const response = await fetch('scraper-radi-caheg6c6g6gcghbf.indonesiacentral-01.azurewebsites.net', {
      // const response = await fetch('http://localhost:8000/api/scrape-stores', {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tasks: validTasks }),
      });

      const data = await response.json();
      
      // LOGIKA NOTIFIKASI PINTAR
      if (data.results && data.results.length > 0) {
        setScrapedData(data.results);
        setShowResults(true); // Otomatis buka dropdown jika ada hasil
        alert(`✅ Scraping selesai! Berhasil menarik ${data.results.length} produk.`);
      } else {
        alert(`ℹ️ Sudah berhasil mengambil informasi toko, tetapi tidak menemukan produk yang cocok. Produk mungkin habis atau tidak dijual di toko tersebut atau nama produknya salah.`);
      }
      
      console.log("Hasil Scrape Toko:", data.results);
    } catch (error) {
      console.error("Error scraping stores:", error);
      alert("❌ Terjadi kesalahan saat menghubungi server.");
    } finally {
      setIsStoreLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-100 p-8 font-sans">
      <div className="max-w-4xl mx-auto space-y-8">
        
        {/* ================= PANEL KONTROL SCRAPING ================= */}
        <div className="bg-white p-6 rounded-lg shadow-md border-t-4 border-orange-500">
          <h1 className="text-3xl font-bold mb-6 text-orange-500">Shopee Scraper by product</h1>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Keyword Produk</label>
              <input 
                type="text" 
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
                className="w-full border border-gray-300 rounded-md p-3 focus:ring-2 focus:ring-orange-500 outline-none"
                placeholder="Misal: iPhone 17"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Target Jumlah</label>
              <input 
                type="number" 
                value={limit}
                onChange={(e) => setLimit(e.target.value)}
                className="w-full border border-gray-300 rounded-md p-3 focus:ring-2 focus:ring-orange-500 outline-none"
                min="1" max="50"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Filter Lokasi Toko</label>
              <select 
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                className="w-full border border-gray-300 rounded-md p-3 bg-white focus:ring-2 focus:ring-orange-500 outline-none"
              >
                <option value="">Semua Lokasi (Default)</option>
                <option value="DKI Jakarta">DKI Jakarta</option>
                <option value="Kota Bandung">Kota Bandung</option>
                <option value="Kota Surabaya">Kota Surabaya</option>
                <option value="Kota Tangerang">Kota Tangerang</option>
                <option value="Kota Medan">Kota Medan</option>
              </select>
            </div>
          </div>

          <button 
            onClick={handleScrape}
            disabled={loading}
            className={`w-full text-white font-bold py-3 px-4 rounded-md transition-colors ${loading ? 'bg-gray-400 cursor-not-allowed' : 'bg-orange-500 hover:bg-orange-600'}`}
          >
            {loading ? 'Sistem Sedang Bekerja, Harap Tunggu...' : 'Mulai Scraping dengan Filter Lokasi'}
          </button>
        </div>


        {/* CARD 3: SCRAPE BERDASARKAN TOKO (DINAMIS) */}
      <div className="bg-white p-6 rounded-lg shadow-md border-t-4 border-green-500 mb-6">
        <h2 className="text-xl font-bold text-green-600 mb-4">
          🏪 Scrape by store and Product of the store
        </h2>

        {storeTasks.map((task, index) => (
          <div key={index} className="flex flex-wrap items-end gap-3 mb-4 p-4 border border-gray-200 rounded relative bg-gray-50">
            {/* Tombol Silang (X) untuk menghapus baris */}
            {storeTasks.length > 1 && (
               <button onClick={() => removeTask(index)} className="absolute top-2 right-3 text-red-500 hover:text-red-700 font-bold">✕</button>
            )}

            <div className="w-full md:w-1/4">
              <label className="block text-xs font-semibold text-gray-600 mb-1">Username Toko*</label>
              <input
                type="text"
                value={task.username}
                onChange={(e) => updateTask(index, 'username', e.target.value)}
                placeholder="Misal: iboxofficial"
                className="w-full border border-gray-300 rounded p-2 focus:border-green-500 text-sm"
              />
            </div>

            <div className="w-full md:w-1/4">
              <label className="block text-xs font-semibold text-gray-600 mb-1">Cari Produk (Opsional)</label>
              <input
                type="text"
                value={task.keyword}
                onChange={(e) => updateTask(index, 'keyword', e.target.value)}
                placeholder="Misal: iPhone 16"
                className="w-full border border-gray-300 rounded p-2 focus:border-green-500 text-sm"
              />
            </div>

            <div className="w-full md:w-1/5">
              <label className="block text-xs font-semibold text-gray-600 mb-1">Target Jumlah</label>
              <input
                type="number"
                value={task.limit}
                onChange={(e) => updateTask(index, 'limit', parseInt(e.target.value))}
                disabled={task.isAll}
                className={`w-full border rounded p-2 text-sm ${task.isAll ? 'bg-gray-200 text-gray-400' : 'border-gray-300 focus:border-green-500'}`}
              />
            </div>

            <div className="w-full md:w-auto flex items-center mb-2 ml-2">
              <input
                type="checkbox"
                checked={task.isAll}
                onChange={(e) => updateTask(index, 'isAll', e.target.checked)}
                className="mr-2 h-4 w-4 text-green-600 cursor-pointer"
              />
              <label className="text-sm text-gray-700 cursor-pointer" onClick={() => updateTask(index, 'isAll', !task.isAll)}>
                Ambil Semua (Get All)
              </label>
            </div>
          </div>
        ))}

        <button onClick={addTask} className="text-sm text-blue-600 font-bold mb-4 hover:underline">
          + Tambah Toko Lain
        </button>

        <button
          onClick={handleStoreScrape}
          disabled={isStoreLoading}
          className={`w-full text-white font-bold py-2 px-4 rounded ${
            isStoreLoading ? "bg-green-300 cursor-not-allowed" : "bg-green-500 hover:bg-green-600"
          }`}
        >
          {isStoreLoading ? "Memproses Data Toko..." : "Mulai Tarik Produk Toko"}
        </button>
      </div>



        {/* ================= PANEL AI ASSISTANT ================= */}
        <div className="bg-white p-6 rounded-lg shadow-md border-t-4 border-blue-500">
          <h2 className="text-2xl font-bold mb-4 text-blue-600">🤖 Konsultan Harga AI</h2>
          
          <div className="mb-4">
            <p className="text-sm font-semibold text-gray-600 mb-2">Pilih Template Cepat:</p>
            <div className="flex flex-wrap gap-2">
              <button 
                onClick={() => handleTemplateClick("Berperanlah sebagai konsultan bisnis. Tolong cari data 'iphone 17' di database maksimal 20 data. Berikan saran harga jual yang bagus untuk menghadapi Mega Sale bulan depan.")}
                className="bg-blue-50 text-blue-700 text-xs font-medium px-3 py-2 rounded border border-blue-200 hover:bg-blue-100 transition"
              >
                Template 1: Strategi Mega Sale
              </button>
              <button 
                onClick={() => handleTemplateClick("Tolong cari data 'iphone 17' maksimal 30 data dari database. Buatkan ringkasan tren harga terendah, rata-rata, dan tertinggi dari berbagai lokasi.")}
                className="bg-purple-50 text-purple-700 text-xs font-medium px-3 py-2 rounded border border-purple-200 hover:bg-purple-100 transition"
              >
                Template 2: Tren Harga Lokasi
              </button>
              <button 
                onClick={() => handleTemplateClick("Cari data kompetitor untuk 'iphone 17' maksimal 50 data di database. Apakah ada outlier (harga yang terlalu murah/mahal yang tidak masuk akal)?")}
                className="bg-green-50 text-green-700 text-xs font-medium px-3 py-2 rounded border border-green-200 hover:bg-green-100 transition"
              >
                Template 3: Deteksi Outlier Harga
              </button>
            </div>
          </div>

          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows="3"
            className="w-full border border-gray-300 rounded-md p-3 focus:ring-2 focus:ring-blue-500 outline-none mb-4 resize-y text-sm"
            placeholder="Ketik instruksi atau pertanyaan untuk AI di sini..."
          ></textarea>

          <button 
            onClick={handleChatAI}
            disabled={aiLoading}
            className={`w-full text-white font-bold py-3 px-4 rounded-md transition-colors ${aiLoading ? 'bg-gray-400 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-700'}`}
          >
            {aiLoading ? 'AI Sedang Membaca Database & Menganalisis...' : 'Kirim ke AI'}
          </button>

          {aiResponse && (
            <div className="mt-6 bg-gray-50 border border-gray-200 rounded-lg p-6">
              <h3 className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-4 border-b pb-2">Hasil Analisis Gemini</h3>
              <div className="text-gray-800 text-sm leading-relaxed">
                {/* Pembaca Markdown dengan Styling Tailwind Kustom */}
                <ReactMarkdown
                  components={{
                    h1: ({node, ...props}) => <h1 className="text-xl font-bold mt-4 mb-2 text-blue-800" {...props} />,
                    h2: ({node, ...props}) => <h2 className="text-lg font-bold mt-4 mb-2 text-blue-700" {...props} />,
                    h3: ({node, ...props}) => <h3 className="text-md font-bold mt-3 mb-1 text-gray-800" {...props} />,
                    p: ({node, ...props}) => <p className="mb-3" {...props} />,
                    ul: ({node, ...props}) => <ul className="list-disc pl-6 mb-3 space-y-1" {...props} />,
                    ol: ({node, ...props}) => <ol className="list-decimal pl-6 mb-3 space-y-1" {...props} />,
                    li: ({node, ...props}) => <li className="" {...props} />,
                    strong: ({node, ...props}) => <strong className="font-semibold text-gray-900" {...props} />,
                  }}
                >
                  {aiResponse}
                </ReactMarkdown>
              </div>
            </div>
          )}
        </div>

{/* ================= PANEL HASIL SCRAPING (DROPDOWN) ================= */}
        {scrapedData.length > 0 && (
          <div className="space-y-4">
            {/* Header Dropdown */}
            <div 
              onClick={() => setShowResults(!showResults)}
              className="flex justify-between items-center bg-white p-4 rounded-lg shadow-sm border-l-4 border-orange-500 cursor-pointer hover:bg-orange-50 transition-colors"
            >
              <h2 className="text-xl font-bold text-gray-800">
                Daftar Produk Terkumpul ({scrapedData.length})
              </h2>
              <span className="text-orange-500 font-bold text-2xl select-none">
                {showResults ? "▲" : "▼"}
              </span>
            </div>
            
            {/* Isi Dropdown (Hanya dirender jika showResults bernilai true) */}
            {showResults && (
              <div className="grid grid-cols-1 gap-6 transition-all duration-300 ease-in-out">
                {scrapedData.map((item, idx) => (
                  <div key={idx} className="bg-white p-5 rounded-lg shadow border border-gray-200 flex flex-col md:flex-row gap-6 hover:shadow-lg transition-shadow">
                    
                    {item.image_url ? (
                      <img src={item.image_url} alt="Produk" className="w-32 h-32 object-cover rounded-md border border-gray-200" />
                    ) : (
                      <div className="w-32 h-32 bg-gray-100 rounded-md flex items-center justify-center text-gray-400 text-sm border border-gray-200">No Image</div>
                    )}
                    
                    <div className="flex-1 min-w-0">
                      <h3 className="font-bold text-lg text-gray-900 mb-1 leading-snug truncate">{item.item_name}</h3>
                      <p className="text-sm font-semibold text-gray-500 mb-3">🏪 Toko: {item.shop_name}</p>
                      
                      <div className="flex flex-wrap items-center gap-3 text-sm text-gray-600 mb-4">
                        <span className="bg-yellow-100 text-yellow-800 px-2.5 py-1 rounded-md font-semibold">⭐ {item.rating_star}</span>
                        <span className="bg-gray-100 text-gray-700 px-2.5 py-1 rounded-md font-medium">{item.total_ratings} Ulasan</span>
                        <span className="bg-orange-100 text-orange-800 px-2.5 py-1 rounded-md font-bold">🔥 Terjual {item.sold}</span>
                        <span className="bg-blue-100 text-blue-800 px-2.5 py-1 rounded-md font-bold">📍 {item.location}</span>
                      </div>
                      
                      <div className="bg-gray-50 rounded-md border border-gray-200 p-4 max-h-48 overflow-y-auto">
                        <p className="font-bold text-xs text-gray-500 mb-3 uppercase tracking-wider border-b border-gray-200 pb-2">Daftar Varian & Harga</p>
                        <ul className="text-sm space-y-2">
                          {item.variants && item.variants.length > 0 ? (
                            item.variants.map((v, vIdx) => (
                              <li key={vIdx} className="flex justify-between items-center group">
                                <span className="text-gray-700">{v.variant_name}</span>
                                <span className="font-bold text-orange-600">Rp {v.price.toLocaleString('id-ID')}</span>
                              </li>
                            ))
                          ) : (
                            <li className="text-gray-400 italic text-center py-2">Tidak ada varian terdeteksi</li>
                          )}
                        </ul>
                      </div>
                    </div>

                  </div>
                ))}
              </div>
            )}
          </div>
        )}

      </div>
    </div>
  );
}