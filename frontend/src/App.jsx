import React, { useState } from 'react';
import './App.css';

export default function App() {
  const [keyword, setKeyword] = useState('');
  const [limit, setLimit] = useState(10);
  const [location, setLocation] = useState(''); // State baru untuk lokasi
  const [loading, setLoading] = useState(false);
  const [scrapedData, setScrapedData] = useState([]);

  const handleScrape = async () => {
    if (!keyword) return alert("Masukkan keyword terlebih dahulu!");
    
    setLoading(true);
    setScrapedData([]);

    try {
        const response = await fetch('http://localhost:8000/api/scrape', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                keyword, 
                limit: parseInt(limit),
                location // Mengirim pilihan lokasi ke backend
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

  return (
    <div className="min-h-screen bg-gray-100 p-8 font-sans">
      <div className="max-w-4xl mx-auto">
        
        {/* PANEL KONTROL */}
        <div className="bg-white p-6 rounded-lg shadow-md mb-8">
          <h1 className="text-3xl font-bold mb-6 text-orange-500">Shopee Scraper Dashboard</h1>
          
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
                min="1" max="20"
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

        {/* PANEL HASIL SCRAPING */}
        {scrapedData.length > 0 && (
          <div className="space-y-6">
            <h2 className="text-xl font-bold text-gray-800">Hasil Scraping ({scrapedData.length} Produk)</h2>
            
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
    </div>
  );
}