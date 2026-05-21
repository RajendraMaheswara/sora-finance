from utils.db import get_db_connection

try:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT 1;")
    print("✅ Koneksi sukses!", cur.fetchone())
    cur.close()
    conn.close()
except Exception as e:
    print("❌ Gagal koneksi:", e)