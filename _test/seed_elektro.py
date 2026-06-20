"""
CRT – Villamos + Gyengeáramú Cikktörzs Seed
Futtatás: py -3.11 _test/seed_elektro.py
Feltölti: categories + products + activities (munkadíj) + prices (listaárak)
"""
import sys, os, uuid
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from env_detect import get_db_url

engine = create_engine(get_db_url(), pool_pre_ping=True)
NOW    = datetime.now()

def uid(): return str(uuid.uuid4())

# ─────────────────────────────────────────────────────────────
# KATEGÓRIA FA
# ─────────────────────────────────────────────────────────────
CATS = [
    # id_kulcs, parent_kulcs, nev, item_class, sort
    ("EROSARAM",   None,         "Erősáramú anyagok",         "materialis", 10),
    ("KAB_NYM",    "EROSARAM",   "NYM kábel",                  "materialis", 11),
    ("KAB_NYY",    "EROSARAM",   "NYY / CYKY kábel",           "materialis", 12),
    ("KAB_VEZ",    "EROSARAM",   "Vezérlőkábel",               "materialis", 13),
    ("MEGSZ",      "EROSARAM",   "Megszakítók, biztosítékok",  "materialis", 14),
    ("KAPCS",      "EROSARAM",   "Kapcsolók, dugaljak",        "materialis", 15),
    ("ELOSZT",     "EROSARAM",   "Elosztók, táblaszerelvény",  "materialis", 16),
    ("CSOVEZ",     "EROSARAM",   "Csővezetékek, kábelcsatorna","materialis", 17),
    ("KAPOCS",     "EROSARAM",   "Kapcsok, kötőelemek",        "materialis", 18),

    ("GYENGAARUM", None,         "Gyengeáramú anyagok",        "materialis", 20),
    ("KAB_GAR",    "GYENGAARUM", "Gyengeáramú kábel",          "materialis", 21),
    ("HALOZAT",    "GYENGAARUM", "Hálózati aktív eszközök",    "materialis", 22),
    ("PASSZ",      "GYENGAARUM", "Passzív hálózat (patch)",    "materialis", 23),
    ("KAMERA",     "GYENGAARUM", "IP kamera rendszerek",       "materialis", 24),
    ("NVR_DVR",    "GYENGAARUM", "NVR / DVR rögzítők",         "materialis", 25),
    ("BELEPTETO",  "GYENGAARUM", "Beléptető rendszer",         "materialis", 26),
    ("TUZJELZO",   "GYENGAARUM", "Tűzjelző rendszer",          "materialis", 27),
    ("RIASZTO",    "GYENGAARUM", "Riasztó rendszer",           "materialis", 28),

    ("MUNKADIJ",   None,         "Munkadíjak",                 "munkadij",   90),
    ("MUNKA_E",    "MUNKADIJ",   "Villanyszerelési munkák",    "munkadij",   91),
    ("MUNKA_G",    "MUNKADIJ",   "Gyengeáramú szerelési munkák","munkadij",  92),
]

# ─────────────────────────────────────────────────────────────
# TERMÉKEK  (crt_code, cat_kulcs, nev, egyseg, ár HUF nettó)
# ─────────────────────────────────────────────────────────────
PRODUCTS = [
    # NYM kábelek
    ("KAB-NYM-1.5-2",   "KAB_NYM", "NYM-J 2×1,5 mm² kábel",         "fm",  285),
    ("KAB-NYM-1.5-3",   "KAB_NYM", "NYM-J 3×1,5 mm² kábel",         "fm",  390),
    ("KAB-NYM-2.5-3",   "KAB_NYM", "NYM-J 3×2,5 mm² kábel",         "fm",  560),
    ("KAB-NYM-2.5-5",   "KAB_NYM", "NYM-J 5×2,5 mm² kábel",         "fm",  890),
    ("KAB-NYM-4-5",     "KAB_NYM", "NYM-J 5×4 mm² kábel",           "fm", 1240),
    ("KAB-NYM-6-5",     "KAB_NYM", "NYM-J 5×6 mm² kábel",           "fm", 1750),

    # NYY / CYKY kábelek
    ("KAB-NYY-4-3",     "KAB_NYY", "NYY-J 3×4 mm² tömör kábel",     "fm",  820),
    ("KAB-NYY-10-4",    "KAB_NYY", "NYY-J 4×10 mm² kábel",          "fm", 2100),
    ("KAB-NYY-16-4",    "KAB_NYY", "NYY-J 4×16 mm² kábel",          "fm", 3200),
    ("KAB-CYKY-1.5-3",  "KAB_NYY", "CYKY 3×1,5 mm² lapos kábel",    "fm",  310),
    ("KAB-CYKY-2.5-3",  "KAB_NYY", "CYKY 3×2,5 mm² lapos kábel",    "fm",  440),

    # Vezérlőkábel
    ("KAB-YCY-2-0.5",   "KAB_VEZ", "YCY 2×0,5 mm² árnyékolt",       "fm",  210),
    ("KAB-YCY-4-0.75",  "KAB_VEZ", "YCY 4×0,75 mm² árnyékolt",      "fm",  340),
    ("KAB-YCY-12-0.75", "KAB_VEZ", "YCY 12×0,75 mm² árnyékolt",     "fm",  780),

    # Megszakítók
    ("MCB-1P-16A-B",    "MEGSZ",   "MCB 1P 16A B-karakterisztika",  "db",  980),
    ("MCB-1P-20A-B",    "MEGSZ",   "MCB 1P 20A B-karakterisztika",  "db",  980),
    ("MCB-1P-32A-C",    "MEGSZ",   "MCB 1P 32A C-karakterisztika",  "db", 1050),
    ("MCB-3P-16A-C",    "MEGSZ",   "MCB 3P 16A C-karakterisztika",  "db", 2800),
    ("MCB-3P-32A-C",    "MEGSZ",   "MCB 3P 32A C-karakterisztika",  "db", 3100),
    ("RCCB-2P-25A",     "MEGSZ",   "Fi-relé 2P 25A 30mA",           "db", 4200),
    ("RCCB-4P-40A",     "MEGSZ",   "Fi-relé 4P 40A 30mA",           "db", 7800),
    ("RCBO-1P-16A",     "MEGSZ",   "RCBO 1P 16A 30mA kombinált",    "db", 5200),

    # Kapcsolók, dugaljak (Legrand Mosaic / Schneider Vivace)
    ("KAPCS-NY-1",      "KAPCS",   "Nyomókapcsoló 1P 10A fehér",    "db",  680),
    ("KAPCS-V-1",       "KAPCS",   "Váltókapcsoló 10A fehér",       "db",  750),
    ("KAPCS-K-1",       "KAPCS",   "Keresztkapcsoló 10A fehér",     "db", 1100),
    ("DUG-SCH-2P",      "KAPCS",   "Schuko dugalj 2P+F fehér",      "db",  820),
    ("DUG-SCH-IP44",    "KAPCS",   "Schuko dugalj IP44 kültéri",    "db", 1650),
    ("DUG-DATA-RJ45",   "KAPCS",   "Adatdugalj RJ45 Cat6 fehér",   "db", 1450),
    ("DUG-TV-F",        "KAPCS",   "TV antenna aljzat F-csatlakozó","db",  890),

    # Elosztók, táblaszerelvény
    ("ELOSZT-8M",       "ELOSZT",  "Elosztótábla 8 modulos süllyesztett","db", 2800),
    ("ELOSZT-18M",      "ELOSZT",  "Elosztótábla 18 modulos felszíni","db", 4200),
    ("ELOSZT-36M-IP65", "ELOSZT",  "Elosztótábla 36M IP65 kültéri", "db",12500),
    ("ELOSZT-DIN-1M",   "ELOSZT",  "DIN-sín 1 méter",              "db",  380),
    ("ELOSZT-N-BAR",    "ELOSZT",  "N-sín 16p",                    "db",  420),
    ("ELOSZT-PE-BAR",   "ELOSZT",  "PE sín 16p",                   "db",  420),

    # Csővezetékek, kábelcsatorna
    ("CSO-PVC-20",      "CSOVEZ",  "PVC villanyszerelési cső Ø20mm","fm",  185),
    ("CSO-PVC-32",      "CSOVEZ",  "PVC villanyszerelési cső Ø32mm","fm",  310),
    ("CSO-FGS-20",      "CSOVEZ",  "Flexibilis gégecsõ Ø20mm",     "fm",  120),
    ("CSATORNA-60x40",  "CSOVEZ",  "Kábelcsatorna 60×40mm fehér",  "fm",  620),
    ("CSATORNA-100x60", "CSOVEZ",  "Kábelcsatorna 100×60mm fehér", "fm",  980),
    ("CSATORNA-160x65", "CSOVEZ",  "Kábelcsatorna 160×65mm fehér", "fm", 1450),

    # Kapcsok
    ("KAPOCS-WAGO-2",   "KAPOCS",  "WAGO 222-412 2-pólusú sorkapocs","db",  85),
    ("KAPOCS-WAGO-3",   "KAPOCS",  "WAGO 222-413 3-pólusú sorkapocs","db", 105),
    ("KAPOCS-WAGO-5",   "KAPOCS",  "WAGO 222-415 5-pólusú sorkapocs","db", 148),
    ("KAPOCS-DIN-4",    "KAPOCS",  "DIN sorkapocs 4mm² kék/szürke", "db",  95),
    ("KAPOCS-DIN-6",    "KAPOCS",  "DIN sorkapocs 6mm²",           "db",  140),

    # Gyengeáramú kábelek
    ("KAB-UTP-CAT6",    "KAB_GAR", "UTP Cat6 kábel szürke 305m",   "tekercs", 32000),
    ("KAB-UTP-CAT6-FM", "KAB_GAR", "UTP Cat6 kábel",               "fm",  105),
    ("KAB-STP-CAT6A",   "KAB_GAR", "S/FTP Cat6A árnyékolt kábel",  "fm",  245),
    ("KAB-KOAX-RG59",   "KAB_GAR", "Koaxkábel RG59 75Ω",          "fm",   98),
    ("KAB-KOAX-RG6",    "KAB_GAR", "Koaxkábel RG6 75Ω árnyékolt",  "fm",  135),
    ("KAB-OPT-MM-4",    "KAB_GAR", "Optikai kábel MM 4x62,5/125µm","fm",  680),
    ("KAB-OPT-SM-4",    "KAB_GAR", "Optikai kábel SM 4x9/125µm",   "fm",  520),
    ("KAB-ANTENNAS",    "KAB_GAR", "Antennakábel H155 50Ω",        "fm",  210),
    ("KAB-2X0.5CCTV",  "KAB_GAR", "Biztonságtechnika kábel 2×0,5","fm",   72),
    ("KAB-8X0.22ALM",  "KAB_GAR", "Riasztó kábel 8×0,22mm²",      "fm",  145),

    # Hálózati aktív eszközök
    ("SW-8P-UNMAN",     "HALOZAT", "8 portos switch menedzselt nélkül","db", 8500),
    ("SW-24P-POE",      "HALOZAT", "24 portos PoE switch menedzselt", "db",68000),
    ("AP-WIFI6-INDOOR", "HALOZAT", "WiFi 6 beltéri access point",    "db",28000),
    ("AP-WIFI6-OUTDR",  "HALOZAT", "WiFi 6 kültéri access point IP67","db",42000),
    ("ROUTER-GW",       "HALOZAT", "Ipari gateway router",           "db",32000),
    ("SFP-MM-1G",       "HALOZAT", "SFP modul 1Gb MM LC 550m",      "db", 4800),
    ("SFP-SM-1G",       "HALOZAT", "SFP modul 1Gb SM LC 20km",      "db", 6200),

    # Passzív hálózat
    ("PATCH-PANEL-24",  "PASSZ",   "Patch panel 24 port Cat6 1U",   "db", 7200),
    ("PATCH-PANEL-48",  "PASSZ",   "Patch panel 48 port Cat6 2U",   "db",12500),
    ("PATCH-RJ45-0.5",  "PASSZ",   "Patch kábel RJ45 Cat6 0,5m",   "db",  480),
    ("PATCH-RJ45-1",    "PASSZ",   "Patch kábel RJ45 Cat6 1m",     "db",  620),
    ("PATCH-RJ45-2",    "PASSZ",   "Patch kábel RJ45 Cat6 2m",     "db",  750),
    ("RACK-6U-WALL",    "PASSZ",   "6U fali rack szekrény 330mm",   "db",18500),
    ("RACK-12U-WALL",   "PASSZ",   "12U fali rack szekrény 450mm",  "db",28000),
    ("RACK-22U-FLOOR",  "PASSZ",   "22U álló rack szekrény 600mm",  "db",68000),
    ("KEYSTONE-RJ45",   "PASSZ",   "Keystone modul RJ45 Cat6 fehér","db",  680),

    # IP kamerák
    ("CAM-IP-DOM-4MP",  "KAMERA",  "IP dóm kamera 4MP PoE IR 30m", "db",14500),
    ("CAM-IP-BULL-8MP", "KAMERA",  "IP bullet kamera 8MP PoE IR 50m","db",22000),
    ("CAM-IP-PTZ-4MP",  "KAMERA",  "IP PTZ forgókamera 4MP 30x",    "db",85000),
    ("CAM-IP-FISH-4K",  "KAMERA",  "IP fisheye kamera 4K 180°",     "db",38000),
    ("CAM-IP-OUT-IP67", "KAMERA",  "IP kültéri kamera IP67 4MP",    "db",18000),
    ("CAM-THERM",       "KAMERA",  "Hőkamera modul IP integrált",   "db",120000),

    # NVR / DVR
    ("NVR-4CH-POE",     "NVR_DVR", "NVR 4 csatornás PoE 1TB",      "db",28000),
    ("NVR-8CH-POE",     "NVR_DVR", "NVR 8 csatornás PoE 2TB",      "db",45000),
    ("NVR-16CH-POE",    "NVR_DVR", "NVR 16 csatornás PoE 4TB",     "db",85000),
    ("HDD-NVR-4TB",     "NVR_DVR", "HDD 4TB NVR dedikált",         "db",22000),

    # Beléptető
    ("BELEPTO-KEZELŐ",  "BELEPTETO","Beléptető kezelőpanel RFID",   "db",32000),
    ("BELEPTO-OLVASO",  "BELEPTETO","RFID kártyaolvasó Wiegand",    "db", 8500),
    ("BELEPTO-ZARAS",   "BELEPTETO","Elektromos zár Fail-Safe 12V", "db",12000),
    ("BELEPTO-KARTYA",  "BELEPTETO","RFID proximity kártya (10db)", "csomag",1800),
    ("BELEPTO-AJTONY",  "BELEPTETO","Ajtónyitó gomb rozsdamentes",  "db", 2800),

    # Tűzjelző
    ("TJ-KOZPONT-4",    "TUZJELZO","Tűzjelző központ 4 hurkos",    "db",85000),
    ("TJ-OPTI-DETO",    "TUZJELZO","Optikai füstérzékelő ABI",     "db", 4200),
    ("TJ-HO-DETO",      "TUZJELZO","Hőérzékelő ABI",               "db", 3800),
    ("TJ-SZIRENABELSO", "TUZJELZO","Beltéri hang-fényjelző",        "db", 6500),
    ("TJ-SZIRENA-KUL",  "TUZJELZO","Kültéri hang-fényjelző IP54",  "db", 9800),
    ("TJ-KEZI-JELZO",   "TUZJELZO","Kézi jelzésadó (törhető))",    "db", 4500),
    ("TJ-KABELT",       "TUZJELZO","JY(St)Y tűzjelző kábel 2×2×0,8","fm",  180),

    # Riasztó
    ("RIA-KOZPONT",     "RIASZTO", "Riasztóközpont 8 zóna GSM",    "db",22000),
    ("RIA-MOZG-PIR",    "RIASZTO", "PIR mozgásérzékelő beltéri",   "db", 4800),
    ("RIA-MOZG-DUAL",   "RIASZTO", "Dual tech érzékelő kültéri",   "db", 8500),
    ("RIA-MAGNKON",     "RIASZTO", "Mágneskontakt ajtóra",         "db",  980),
    ("RIA-SZIRENAB",    "RIASZTO", "Beltéri piezo sziréna",        "db", 2800),
    ("RIA-KLAVIATURA",  "RIASZTO", "LCD kezelő billentyűzettel",   "db", 9500),
    ("RIA-AKKUM-12V",   "RIASZTO", "Akkumulátor 12V 7Ah riasztóhoz","db", 2800),
]

# ─────────────────────────────────────────────────────────────
# MUNKADÍJAK  (activities táblába)
# ─────────────────────────────────────────────────────────────
ACTIVITIES = [
    # crt_code, cat_kulcs, nev, egyseg, ár nettó HUF
    # Villanyszerelési munkák
    ("MUNKA-VIL-ORA",   "MUNKA_E", "Villanyszerelő óradíj",              "óra",  8500),
    ("MUNKA-KAB-FM",    "MUNKA_E", "Kábelfektetés cső nélkül",           "fm",    650),
    ("MUNKA-KAB-CSOS",  "MUNKA_E", "Kábelfektetés csőben",               "fm",    950),
    ("MUNKA-CSATORNA",  "MUNKA_E", "Kábelcsatorna szerelés",             "fm",    780),
    ("MUNKA-DOBOZ-F",   "MUNKA_E", "Doboz süllyesztés falba (kő/beton)", "db",  1800),
    ("MUNKA-DOBOZ-GK",  "MUNKA_E", "Doboz szerelés gipszkartonba",       "db",   950),
    ("MUNKA-DUGG",      "MUNKA_E", "Dugalj/kapcsoló felszerelés",        "db",   850),
    ("MUNKA-TABLA-1M",  "MUNKA_E", "Elosztótábla szerelés (1 modul)",    "db",   450),
    ("MUNKA-TABLA-KOMP","MUNKA_E", "Tábla teljes bekötés + próba",       "óra", 12000),
    ("MUNKA-FEL-CSILL", "MUNKA_E", "Lámpatest felszerelés",              "db",  1200),
    ("MUNKA-REVIZIO",   "MUNKA_E", "Villamos felülvizsgálat",            "óra", 10000),
    ("MUNKA-FUR-BETON", "MUNKA_E", "Átfúrás betonon (20-50mm)",          "db",  2500),
    ("MUNKA-VEZER",     "MUNKA_E", "Vezérlés bekötés + programozás",     "óra", 12000),

    # Gyengeáramú szerelési munkák
    ("MUNKA-GAR-ORA",   "MUNKA_G", "Gyengeáramú szerelő óradíj",         "óra",  9000),
    ("MUNKA-UTP-FM",    "MUNKA_G", "UTP kábelfektetés (100m-ig)",        "fm",    420),
    ("MUNKA-PATCH-DP",  "MUNKA_G", "Patch panel pontbecsatlakozás",      "db",   350),
    ("MUNKA-SZEKI-CAT6","MUNKA_G", "Keystone betáncolás + tesztelés",    "db",   480),
    ("MUNKA-RACK-SZER", "MUNKA_G", "Rack szekrény telepítés + rendezés", "óra", 10000),
    ("MUNKA-CAM-FELSZER","MUNKA_G","IP kamera felszerelés + bekötés",    "db",  3500),
    ("MUNKA-CAM-BEALL", "MUNKA_G", "Kamera beállítás (szög, fókusz)",    "db",  1500),
    ("MUNKA-NVR-KONF",  "MUNKA_G", "NVR konfiguráció + felvételbeállítás","db", 5000),
    ("MUNKA-BELEPTO-P", "MUNKA_G", "Beléptető pont telepítés (zár+olv.)","db", 8500),
    ("MUNKA-TJ-PONT",   "MUNKA_G", "Tűzjelző érzékelő telepítés",       "db",  2200),
    ("MUNKA-TJ-PROG",   "MUNKA_G", "Tűzjelző programozás + átadás",     "óra", 14000),
    ("MUNKA-RIA-ZONA",  "MUNKA_G", "Riasztó zóna telepítés",             "db",  1800),
    ("MUNKA-RIA-PROG",  "MUNKA_G", "Riasztó programozás + próba",        "óra", 11000),
    ("MUNKA-OPTIKA",    "MUNKA_G", "Optikai kábel végezés (csatlakozó)", "db",  3500),
    ("MUNKA-OPTIKA-SW", "MUNKA_G", "Optikai hegesztés (splicer)",        "db",  2800),
]

# ─────────────────────────────────────────────────────────────
# BETÖLTÉS
# ─────────────────────────────────────────────────────────────
def load():
    cat_ids = {}   # kulcs → uuid

    with engine.begin() as conn:
        # 1) Kategóriák
        for key, parent_key, name, item_class, sort in CATS:
            existing = conn.execute(text(
                "SELECT category_id FROM categories WHERE name=:n"
            ), {"n": name}).fetchone()
            if existing:
                cat_ids[key] = existing[0]
                print(f"  [skip] kategória: {name}")
                continue
            cid = uid()
            pid = cat_ids.get(parent_key) if parent_key else None
            conn.execute(text(
                "INSERT INTO categories (category_id,parent_id,name,item_class,sort_order,active) "
                "VALUES (:cid,:pid,:name,:ic,:so,true)"
            ), {"cid": cid, "pid": pid, "name": name, "ic": item_class, "so": sort})
            cat_ids[key] = cid
            print(f"  [+] kategória: {name}")

        # 2) Termékek
        prod_count = 0
        for crt_code, cat_key, name, unit, net_price in PRODUCTS:
            existing = conn.execute(text(
                "SELECT item_id FROM products WHERE crt_code=:c"
            ), {"c": crt_code}).fetchone()
            if existing:
                item_id = existing[0]
            else:
                item_id = uid()
                conn.execute(text(
                    "INSERT INTO products "
                    "(item_id,crt_code,name,unit,category_id,item_class,active,created_at) "
                    "VALUES (:iid,:code,:name,:unit,:cid,'materialis',true,:now)"
                ), {"iid": item_id, "code": crt_code, "name": name,
                    "unit": unit, "cid": cat_ids.get(cat_key), "now": NOW})

            # Listaár UPSERT
            ex_price = conn.execute(text(
                "SELECT price_id FROM prices "
                "WHERE item_id=:iid AND price_type='lista' AND source='seed'"
            ), {"iid": item_id}).fetchone()
            if not ex_price:
                conn.execute(text(
                    "INSERT INTO prices "
                    "(price_id,item_id,item_class,price_type,net_price,currency,"
                    " valid_from,db_inserted,source) "
                    "VALUES (:pid,:iid,'materialis','lista',:price,'HUF',:now,:now,'seed')"
                ), {"pid": uid(), "iid": item_id, "price": net_price, "now": NOW})
                prod_count += 1
            else:
                conn.execute(text(
                    "UPDATE prices SET net_price=:p WHERE price_id=:pid"
                ), {"p": net_price, "pid": ex_price[0]})
                prod_count += 1

        # 3) Munkadíjak (activities)
        act_count = 0
        for crt_code, cat_key, name, unit, net_price in ACTIVITIES:
            existing = conn.execute(text(
                "SELECT item_id FROM activities WHERE crt_code=:c"
            ), {"c": crt_code}).fetchone()
            if existing:
                item_id = existing[0]
            else:
                item_id = uid()
                conn.execute(text(
                    "INSERT INTO activities "
                    "(item_id,crt_code,name,unit,category_id,active,created_at) "
                    "VALUES (:iid,:code,:name,:unit,:cid,true,:now)"
                ), {"iid": item_id, "code": crt_code, "name": name,
                    "unit": unit, "cid": cat_ids.get(cat_key), "now": NOW})

            # Listaár
            ex_price = conn.execute(text(
                "SELECT price_id FROM prices "
                "WHERE item_id=:iid AND price_type='lista' AND source='seed'"
            ), {"iid": item_id}).fetchone()
            if not ex_price:
                conn.execute(text(
                    "INSERT INTO prices "
                    "(price_id,item_id,item_class,price_type,net_price,currency,"
                    " valid_from,db_inserted,source) "
                    "VALUES (:pid,:iid,'munkadij','lista',:price,'HUF',:now,:now,'seed')"
                ), {"pid": uid(), "iid": item_id, "price": net_price, "now": NOW})
            else:
                conn.execute(text(
                    "UPDATE prices SET net_price=:p WHERE price_id=:pid"
                ), {"p": net_price, "pid": ex_price[0]})
            act_count += 1

    print(f"\n  Kesz: {len(CATS)} kategoria, {prod_count} termek ar, {act_count} munkadij ar betoltve.")

if __name__ == "__main__":
    print("\nCRT Villamos + Gyengeáramú Cikktörzs Seed\n")
    load()
    print("  Minden rendben.\n")
