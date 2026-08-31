import React, { useState } from 'react';

export default function App() {
  const [keyword, setKeyword] = useState('');
  const [limit, setLimit] = useState(10);
  const [loading, setLoading] = useState(false);
  const [scrapedData, setScrapedData] = useState([]);

  const handleScrape = async () => {
    if (!keyword) return alert("Masukkan keyword terlebih dahulu!");
    
    setLoading(true);
    setScrapedData([]); // Kosongkan data sebelumnya

    try {
        const response = await fetch('http://localhost:8000/api/scrape', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ keyword, limit: parseInt(limit) })
        });
        
        const data = await response.json();
        setScrapedData(data.results);
        alert("Scraping berhasil diselesaikan!");
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
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Keyword Produk</label>
              <input 
                type="text" 
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
                className="w-full border border-gray-300 rounded-md p-3"
                placeholder="Misal: Lipstik Matte"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Jumlah Target Halaman</label>
              <input 
                type="number" 
                value={limit}
                onChange={(e) => setLimit(e.target.value)}
                className="w-full border border-gray-300 rounded-md p-3"
                min="1" max="20"
              />
            </div>
          </div>

          <button 
            onClick={handleScrape}
            disabled={loading}
            className={`w-full text-white font-bold py-3 px-4 rounded-md transition-colors ${loading ? 'bg-gray-400 cursor-not-allowed' : 'bg-orange-500 hover:bg-orange-600'}`}
          >
            {loading ? 'Sistem Sedang Bekerja, Harap Tunggu...' : 'Mulai Scraping Otomatis'}
          </button>
        </div>

        {/* PANEL HASIL SCRAPING */}
        {scrapedData.length > 0 && (
          <div className="space-y-6">
            <h2 className="text-xl font-bold text-gray-800">Hasil Scraping ({scrapedData.length} Produk)</h2>
            
            {scrapedData.map((item, idx) => (
              <div key={idx} className="bg-white p-5 rounded-lg shadow border border-gray-200 flex flex-col md:flex-row gap-6">
                
                {/* Gambar Produk */}
                {item.image_url ? (
                  <img src={item.image_url} alt="Produk" className="w-32 h-32 object-cover rounded-md border" />
                ) : (
                  <div className="w-32 h-32 bg-gray-200 rounded-md flex items-center justify-center text-gray-400 text-sm">No Image</div>
                )}
                
                {/* Info Utama */}
                <div className="flex-1">
                  <h3 className="font-bold text-lg text-gray-900 mb-2 leading-tight">{item.item_name}</h3>
                  <div className="flex flex-wrap items-center gap-3 text-sm text-gray-600 mb-4">
                    <span className="bg-yellow-100 text-yellow-800 px-2.5 py-1 rounded-md font-semibold flex items-center gap-1">
                      ⭐ {item.rating_star}
                    </span>
                    <span className="bg-gray-100 text-gray-700 px-2.5 py-1 rounded-md font-medium">
                      {item.total_ratings} Ulasan
                    </span>
                    <span className="bg-orange-100 text-orange-800 px-2.5 py-1 rounded-md font-bold flex items-center gap-1">
                      🔥 Terjual {item.sold}
                    </span>
                    {/* Tambahkan badge lokasi di bawah ini */}
                    <span className="bg-blue-100 text-blue-800 px-2.5 py-1 rounded-md font-bold flex items-center gap-1">
                      📍 {item.location}
                    </span>
                  </div>
                  
                  {/* Daftar Varian (Scrollable jika terlalu banyak) */}
                  <div className="bg-gray-50 rounded border p-3 max-h-40 overflow-y-auto">
                    <p className="font-semibold text-xs text-gray-500 mb-2 uppercase">Varian & Harga (Rp)</p>
                    <ul className="text-sm space-y-1">
                      {item.variants.length > 0 ? (
                        item.variants.map((v, vIdx) => (
                          <li key={vIdx} className="flex justify-between border-b border-gray-100 pb-1">
                            <span>{v.variant_name}</span>
                            <span className="font-medium text-orange-600">{v.price.toLocaleString('id-ID')}</span>
                          </li>
                        ))
                      ) : (
                        <li className="text-gray-400 italic">Tidak ada varian</li>
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