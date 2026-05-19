from flask import Flask, request, jsonify

app = Flask(__name__)

# Ini adalah rute/jembatan yang akan dipanggil oleh Golang
@app.route('/api/predict', methods=['POST'])
def hitung_forecast():
    # 1. Menerima kiriman data dari Golang (biasanya bentuk JSON)
    data_masuk = request.json
    print("Data dari Golang berhasil diterima:", data_masuk)
    
    # --- TEMPAT NGODING NANTI ---
    # Di sini akan pakai algoritma (misal: Moving Average / Prophet)
    # menggunakan variabel 'data_masuk'
    # ------------------------------------

    # 2. Membuat jawaban sementara (dummy) untuk dikembalikan ke Golang
    jawaban_ke_golang = {
        "status": "sukses",
        "pesan": "Ini adalah balasan dari Python!",
        "hasil_forecast": [100, 200, 300], # Contoh output
        "data_yang_kamu_kirim": data_masuk
    }
    
    return jsonify(jawaban_ke_golang)

if __name__ == '__main__':
    # Menjalankan server Python di port 5000
    app.run(port=5000, debug=True)