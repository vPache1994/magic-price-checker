from flask import Flask, request, jsonify, render_template
import requests
from requests_oauthlib import OAuth1
import json, os
from config import APP_TOKEN, APP_SECRET, ACCESS_TOKEN, ACCESS_SECRET

app = Flask(__name__)
auth = OAuth1(APP_TOKEN, APP_SECRET, ACCESS_TOKEN, ACCESS_SECRET)

DB_FILE = "cards_db.json"

# Cargar base offline
if os.path.exists(DB_FILE):
    with open(DB_FILE, "r", encoding="utf-8") as f:
        cardDB = json.load(f)
else:
    cardDB = {}

def guardar_db():
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(cardDB, f, ensure_ascii=False, indent=4)

# Mapas de ejemplo para CardMarket (IDs reales según API)
condition_map = {"NM":1, "LP":2, "MP":3, "HP":4}
language_map = {"en":1, "es":2, "de":3}

def buscar_carta_cardmarket(nombre, idioma="", estado="", foil=None, set_name=""):
    url = "https://api.cardmarket.com/ws/v2.0/output.json/products"
    params = {"search": nombre, "idGame": 1, "start": 0, "maxResults": 10}

    if idioma: params["idLanguage"] = language_map.get(idioma.lower(), "")
    if estado: params["idCondition"] = condition_map.get(estado.upper(), "")
    if foil is not None: params["isFoil"] = foil
    if set_name: params["idExpansion"] = set_name  # requiere ID real del set

    try:
        response = requests.get(url, auth=auth, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            products = data.get("product", [])
            results = []
            if isinstance(products, dict):
                products = [products]  # si solo viene uno
            for prod in products:
                precio = float(prod["priceGuide"]["LOW"])
                results.append({
                    "nombre": prod["enName"],
                    "precio": precio,
                    "compra": round(precio - 0.05, 2),
                    "venta": round(precio + 0.10, 2),
                    "rarity": prod.get("rarity", "comun"),
                    "language": idioma or "en",
                    "foil": foil if foil is not None else False,
                    "condition": estado or "NM",
                    "set": set_name
                })
            return results
    except Exception as e:
        print("Error API CardMarket:", e)
    return []

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/precio", methods=["GET"])
def precio():
    nombre = request.args.get("nombre", "").strip()
    idioma = request.args.get("idioma", "").strip()
    estado = request.args.get("estado", "").strip()
    foil = request.args.get("foil", "").strip()
    set_name = request.args.get("set", "").strip()

    foil_val = None
    if foil.lower() == "true":
        foil_val = True
    elif foil.lower() == "false":
        foil_val = False

    cartas_finales = []
    print("Base offline actual:", cardDB)


    # 1️⃣ Buscar en API
    api_results = buscar_carta_cardmarket(nombre, idioma, estado, foil_val, set_name)
    if api_results:
        for carta in api_results:
            # Guardar en base offline si no existe
            if carta["nombre"].lower() not in (k.lower() for k in cardDB):
                cardDB[carta["nombre"]] = {
                    "price": carta["precio"],
                    "rarity": carta["rarity"],
                    "language": carta["language"],
                    "foil": carta["foil"],
                    "condition": carta["condition"],
                    "set": carta["set"]
                }
                guardar_db()
            cartas_finales.append({
                "nombre": carta["nombre"],
                "precio": carta["precio"],
                "compra": carta["compra"],
                "venta": carta["venta"],
                "rarity": carta["rarity"],
                "language": carta["language"],
                "foil": carta["foil"],
                "condition": carta["condition"],
                "set": carta["set"]
            })

    # 2️⃣ Si no hay resultados en API, buscar en base offline
    if not cartas_finales:
        for key, value in cardDB.items():
            if key.strip().lower() == nombre.strip().lower():
                precio_val = value.get("price", value.get("precio", 0))
                cartas_finales.append({
                    "nombre": key,
                    "precio": precio_val,
                    "compra": round(precio_val - 0.05,2),
                    "venta": round(precio_val + 0.10,2),
                    "rarity": value.get("rarity", "comun"),
                    "language": value.get("language", "en"),
                    "foil": value.get("foil", False),
                    "condition": value.get("condition", "NM"),
                    "set": value.get("set", "")
                })
                break

    if cartas_finales:
        return jsonify(cartas_finales)
    else:
        return jsonify({"error": "Carta no encontrada"}), 404

if __name__ == "__main__":
    app.run(debug=True)
