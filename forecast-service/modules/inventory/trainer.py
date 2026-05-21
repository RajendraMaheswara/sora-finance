import pandas as pd
import requests
from config import Config
from modules.inventory.forecaster import InventoryForecaster

def train_all_inventory_models():
    url = f"{Config.BACKEND_API_URL}/ingredient-stock-histories"
    try:
        resp = requests.get(url)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"Gagal mengambil data dari API: {e}")
        return

    data = resp.json()
    if isinstance(data, dict) and 'data' in data:
        records = data['data']
    else:
        records = data

    if not records:
        print("Tidak ada data ingredient stock histories.")
        return

    df = pd.DataFrame(records)
    # Ambil pasangan unik
    pairs = df[['m_store_id', 'm_food_ingredient_id']].drop_duplicates()

    for _, row in pairs.iterrows():
        store_id = row['m_store_id']
        ingr_id = row['m_food_ingredient_id']
        print(f"Training model untuk Store {store_id}, Ingredient {ingr_id}...")
        try:
            fc = InventoryForecaster(store_id, ingr_id)
            fc.tune_and_train()
        except Exception as e:
            print(f"Gagal training {store_id}-{ingr_id}: {e}")