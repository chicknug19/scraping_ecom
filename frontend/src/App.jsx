import { useState, useEffect } from 'react'

function App() {
  const [data, setData] = useState([])

  useEffect(() => {
    // Memanggil endpoint FastAPI (Pastikan backend sedang jalan)
    fetch('http://localhost:8000/api/products')
      .then(res => res.json())
      .then(result => {
        if(result.status === "success") {
          setData(result.data)
        }
      })
      .catch(err => console.error("Gagal mengambil data:", err))
  }, [])

  return (
    <div style={{ padding: '20px', fontFamily: 'Arial' }}>
      <h1>Pricing Dashboard (Shopee & Tokopedia)</h1>
      <table border="1" cellPadding="10">
        <thead>
          <tr>
            <th>Date</th>
            <th>Item Name</th>
            <th>Price</th>
            <th>Seller</th>
          </tr>
        </thead>
        <tbody>
          {data.map((item, index) => (
            <tr key={index}>
              <td>{item.dtime}</td>
              <td>{item.ItemName}</td>
              <td>{item.Price}</td>
              <td>{item.Seller}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default App