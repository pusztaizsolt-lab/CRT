"""
CRT Cikktörzs seed v0.1 — teszt adatok
=======================================
20 valós termék: 10 villamos anyag + 10 vagyonvédelmi
  • Kábelek   : típus, keresztmetszet, szigetelő, erek, amper, alkalmazás
  • Kismegszakítók: karakterisztika, pólusszám, névleges áram, megszakítóképesség, IP
  • Vagyonvédelmi : típus, zónák/csatornák, kommunikáció, IP védelem, feszültség

Árak: nettó nagyker / nettó kisker → bruttó = nettó × 1.27 (27% ÁFA)

Futtatás: py -3.11 _test/seed_cikktorzs_01.py
Előfeltétel: py -3.11 db_migrate_v06.py (specs + gross_price + price_tier oszlopok)
"""
import uuid, sys, os
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from sqlalchemy import create_engine, text
from env_detect import get_db_url

engine = create_engine(get_db_url(), pool_pre_ping=True)
NOW    = datetime.now(timezone.utc)
VAT    = 27.0   # Magyar ÁFA %

# ── KATEGÓRIÁK ───────────────────────────────────────────────────────────────

CATS = [
    {"id": "cat-elek",     "parent": None,       "name": "Elektromos anyagok", "class": "materialis"},
    {"id": "cat-kabel",    "parent": "cat-elek",  "name": "Kábelek",            "class": "materialis"},
    {"id": "cat-megsz",    "parent": "cat-elek",  "name": "Kismegszakítók",     "class": "materialis"},
    {"id": "cat-vagyon",   "parent": None,        "name": "Vagyonvédelmi",      "class": "materialis"},
    {"id": "cat-riaszto",  "parent": "cat-vagyon","name": "Riasztórendszerek",  "class": "materialis"},
    {"id": "cat-kamera",   "parent": "cat-vagyon","name": "Kamerák",            "class": "materialis"},
]

# ── TERMÉKEK ─────────────────────────────────────────────────────────────────
# Minden termék: crt_code, name, unit, category_id, specs, nagyker_netto, kisker_netto

PRODUCTS = [

    # ──── KÁBELEK ────────────────────────────────────────────────────────────
    {
        "crt_code": "K-001",
        "name":     "NYM-J 3×1,5 mm² erősáramú kábel",
        "unit":     "m",
        "cat":      "cat-kabel",
        "model":    "NYM-J 3x1.5",
        "specs": {
            "kabel_tipus":      "NYM-J",
            "keresztmetszet_mm2": 1.5,
            "szigetelo":        "PVC",
            "erek_szama":       3,
            "amper_A":          16,
            "alkalmazas":       ["beltéri", "falba fektetett", "vakolat alatti"],
            "szin":             "szürke",
            "szabvany":         "MSZ HD 21.5 S3",
            "max_feszultseg_V": 300,
        },
        "nagyker_netto": 285,
        "kisker_netto":  390,
    },
    {
        "crt_code": "K-002",
        "name":     "NYM-J 3×2,5 mm² erősáramú kábel",
        "unit":     "m",
        "cat":      "cat-kabel",
        "model":    "NYM-J 3x2.5",
        "specs": {
            "kabel_tipus":      "NYM-J",
            "keresztmetszet_mm2": 2.5,
            "szigetelo":        "PVC",
            "erek_szama":       3,
            "amper_A":          20,
            "alkalmazas":       ["beltéri", "falba fektetett", "vakolat alatti"],
            "szin":             "szürke",
            "szabvany":         "MSZ HD 21.5 S3",
            "max_feszultseg_V": 300,
        },
        "nagyker_netto": 385,
        "kisker_netto":  525,
    },
    {
        "crt_code": "K-003",
        "name":     "NYM-J 5×2,5 mm² erősáramú kábel",
        "unit":     "m",
        "cat":      "cat-kabel",
        "model":    "NYM-J 5x2.5",
        "specs": {
            "kabel_tipus":      "NYM-J",
            "keresztmetszet_mm2": 2.5,
            "szigetelo":        "PVC",
            "erek_szama":       5,
            "amper_A":          20,
            "alkalmazas":       ["beltéri", "háromfázisú körök", "motoros terhelés"],
            "szin":             "szürke",
            "szabvany":         "MSZ HD 21.5 S3",
            "max_feszultseg_V": 300,
        },
        "nagyker_netto": 625,
        "kisker_netto":  860,
    },
    {
        "crt_code": "K-004",
        "name":     "NYY-J 3×2,5 mm² földkábel",
        "unit":     "m",
        "cat":      "cat-kabel",
        "model":    "NYY-J 3x2.5",
        "specs": {
            "kabel_tipus":      "NYY-J",
            "keresztmetszet_mm2": 2.5,
            "szigetelo":        "PVC",
            "erek_szama":       3,
            "amper_A":          20,
            "alkalmazas":       ["kültéri", "földbe fektethető", "nedves helyiség"],
            "szin":             "fekete",
            "szabvany":         "MSZ HD 603-1",
            "max_feszultseg_V": 600,
            "foldelheto":       True,
        },
        "nagyker_netto": 458,
        "kisker_netto":  630,
    },
    {
        "crt_code": "K-005",
        "name":     "H07V-K 1×4 mm² flexibilis kapcsolóvezeték piros",
        "unit":     "m",
        "cat":      "cat-kabel",
        "model":    "H07V-K 1x4",
        "specs": {
            "kabel_tipus":      "H07V-K",
            "keresztmetszet_mm2": 4.0,
            "szigetelo":        "PVC",
            "erek_szama":       1,
            "amper_A":          32,
            "alkalmazas":       ["kapcsolótábla", "elosztó belső bekötés", "flexibilis"],
            "szin":             "piros",
            "szabvany":         "MSZ EN 50525-2-31",
            "max_feszultseg_V": 450,
            "hajlekony":        True,
        },
        "nagyker_netto": 195,
        "kisker_netto":  268,
    },

    # ──── KISMEGSZAKÍTÓK ─────────────────────────────────────────────────────
    {
        "crt_code": "M-001",
        "name":     "Schneider iC60N 1P B16A kismegszakító",
        "unit":     "db",
        "cat":      "cat-megsz",
        "model":    "A9F03116",
        "specs": {
            "gyarto":               "Schneider Electric",
            "sorozat":              "iC60N",
            "polus":                "1P",
            "nev_aram_A":           16,
            "karakterisztika":      "B",
            "megszakito_kep_kA":    6.0,
            "vedett_km2_min":       1.0,
            "vedett_km2_max":       2.5,
            "ip_vedelem":           "IP20",
            "din_sinre":            True,
            "aram_tipusa":          "AC",
            "melyseg_mm":           78,
            "alkalmazas":           ["lakóépület", "fénykör", "dugalj kör"],
        },
        "nagyker_netto": 2850,
        "kisker_netto":  4250,
    },
    {
        "crt_code": "M-002",
        "name":     "Schneider iC60N 1P C16A kismegszakító",
        "unit":     "db",
        "cat":      "cat-megsz",
        "model":    "A9F74116",
        "specs": {
            "gyarto":               "Schneider Electric",
            "sorozat":              "iC60N",
            "polus":                "1P",
            "nev_aram_A":           16,
            "karakterisztika":      "C",
            "megszakito_kep_kA":    6.0,
            "vedett_km2_min":       1.5,
            "vedett_km2_max":       4.0,
            "ip_vedelem":           "IP20",
            "din_sinre":            True,
            "aram_tipusa":          "AC",
            "melyseg_mm":           78,
            "alkalmazas":           ["dugalj kör", "motor", "transzformátor"],
        },
        "nagyker_netto": 2850,
        "kisker_netto":  4250,
    },
    {
        "crt_code": "M-003",
        "name":     "Schneider iC60N 1P C25A kismegszakító",
        "unit":     "db",
        "cat":      "cat-megsz",
        "model":    "A9F74125",
        "specs": {
            "gyarto":               "Schneider Electric",
            "sorozat":              "iC60N",
            "polus":                "1P",
            "nev_aram_A":           25,
            "karakterisztika":      "C",
            "megszakito_kep_kA":    6.0,
            "vedett_km2_min":       2.5,
            "vedett_km2_max":       6.0,
            "ip_vedelem":           "IP20",
            "din_sinre":            True,
            "aram_tipusa":          "AC",
            "alkalmazas":           ["mosógép", "villanytűzhely", "klíma"],
        },
        "nagyker_netto": 3100,
        "kisker_netto":  4620,
    },
    {
        "crt_code": "M-004",
        "name":     "ABB SH201-C16 1P C16A kismegszakító",
        "unit":     "db",
        "cat":      "cat-megsz",
        "model":    "2CDS211001R0164",
        "specs": {
            "gyarto":               "ABB",
            "sorozat":              "SH200L",
            "polus":                "1P",
            "nev_aram_A":           16,
            "karakterisztika":      "C",
            "megszakito_kep_kA":    4.5,
            "vedett_km2_min":       1.5,
            "vedett_km2_max":       4.0,
            "ip_vedelem":           "IP20",
            "din_sinre":            True,
            "aram_tipusa":          "AC",
            "alkalmazas":           ["lakóépület", "gazdaságos megoldás"],
        },
        "nagyker_netto": 1820,
        "kisker_netto":  2650,
    },
    {
        "crt_code": "M-005",
        "name":     "Legrand TX3 3P C32A kismegszakító",
        "unit":     "db",
        "cat":      "cat-megsz",
        "model":    "403577",
        "specs": {
            "gyarto":               "Legrand",
            "sorozat":              "TX3",
            "polus":                "3P",
            "nev_aram_A":           32,
            "karakterisztika":      "C",
            "megszakito_kep_kA":    6.0,
            "vedett_km2_min":       4.0,
            "vedett_km2_max":       10.0,
            "ip_vedelem":           "IP20",
            "din_sinre":            True,
            "aram_tipusa":          "AC",
            "szelesseg_modul":      3,
            "alkalmazas":           ["háromfázisú motor", "ipari", "klíma berendezés"],
        },
        "nagyker_netto": 7850,
        "kisker_netto":  11200,
    },

    # ──── VAGYONVÉDELMI ──────────────────────────────────────────────────────
    {
        "crt_code": "V-001",
        "name":     "Paradox MG5050 riasztóközpont 50 zóna",
        "unit":     "db",
        "cat":      "cat-riaszto",
        "model":    "MG5050",
        "specs": {
            "gyarto":           "Paradox",
            "zonak_szama":      50,
            "kommunikacio":     ["GSM", "PSTN", "IP opcionális"],
            "ip_vedelem":       "IP20",
            "tapfeszultseg_V":  "12V DC akkumulátor + 230V AC adapter",
            "kimenet_db":       4,
            "felhasznalok":     32,
            "memoriapontok":    500,
            "buszos":           True,
            "alkalmazas":       ["lakóingatlan", "kisiroda", "raktár"],
        },
        "nagyker_netto": 28500,
        "kisker_netto":  42000,
    },
    {
        "crt_code": "V-002",
        "name":     "Ajax Hub 2 riasztóközpont",
        "unit":     "db",
        "cat":      "cat-riaszto",
        "model":    "Hub 2",
        "specs": {
            "gyarto":           "Ajax Systems",
            "zonak_szama":      100,
            "kommunikacio":     ["Ethernet", "GSM 2G/3G/4G (SIM)"],
            "ip_vedelem":       "IP20",
            "tapfeszultseg_V":  "12V DC belső akku",
            "detektorok_max":   100,
            "felhasznalok":     99,
            "titkositas":       "AES-128",
            "ertesites":        ["app", "SMS", "hívás"],
            "alkalmazas":       ["modern lakás", "iroda", "kisbolt"],
        },
        "nagyker_netto": 32500,
        "kisker_netto":  48000,
    },
    {
        "crt_code": "V-003",
        "name":     "Bosch DS151i PIR mozgásérzékelő beltéri",
        "unit":     "db",
        "cat":      "cat-riaszto",
        "model":    "DS151i",
        "specs": {
            "gyarto":           "Bosch Security",
            "technologia":      "PIR",
            "lefedes_szog":     "90°",
            "lefedes_tavolsag_m": 12,
            "ip_vedelem":       "IP20",
            "tapfeszultseg_V":  "9-15V DC",
            "tampervedelem":    True,
            "becsusgato":       False,
            "alkalmazas":       ["beltéri sarokba szerelés", "lakás", "iroda"],
        },
        "nagyker_netto": 4850,
        "kisker_netto":  7200,
    },
    {
        "crt_code": "V-004",
        "name":     "Hikvision DS-2CD2143G2-I 4MP AcuSense IP kamera",
        "unit":     "db",
        "cat":      "cat-kamera",
        "model":    "DS-2CD2143G2-I",
        "specs": {
            "gyarto":           "Hikvision",
            "felbontas_MP":     4,
            "optika_mm":        2.8,
            "ir_tavolsag_m":    40,
            "ip_vedelem":       "IP67",
            "taplaltas":        ["PoE (802.3af)", "12V DC"],
            "video_tomoritoo":  "H.265+/H.265/H.264+/H.264",
            "sd_kartya":        "max 256GB",
            "ai_funkciok":      ["emberdetekció", "autódetekció"],
            "alkalmazas":       ["kültéri", "beltéri", "belépő zóna"],
        },
        "nagyker_netto": 14800,
        "kisker_netto":  21500,
    },
    {
        "crt_code": "V-005",
        "name":     "Dahua IPC-HDW2849H-S-IL 8MP Smart Dual Light IP kamera",
        "unit":     "db",
        "cat":      "cat-kamera",
        "model":    "IPC-HDW2849H-S-IL",
        "specs": {
            "gyarto":           "Dahua",
            "felbontas_MP":     8,
            "optika_mm":        2.8,
            "ir_tavolsag_m":    30,
            "feher_feny_m":     30,
            "ip_vedelem":       "IP67",
            "taplaltas":        ["PoE (802.3af)", "12V DC"],
            "video_tomoritoo":  "H.265+/H.265/H.264+",
            "sd_kartya":        "max 256GB",
            "szin_ejjel":       True,
            "alkalmazas":       ["kültéri rögzítés", "raktár", "udvar"],
        },
        "nagyker_netto": 16900,
        "kisker_netto":  24800,
    },
    {
        "crt_code": "V-006",
        "name":     "Paradox EVO192 riasztóközpont 192 zóna",
        "unit":     "db",
        "cat":      "cat-riaszto",
        "model":    "EVO192",
        "specs": {
            "gyarto":           "Paradox",
            "zonak_szama":      192,
            "kommunikacio":     ["PSTN", "IP modul opcionális", "GSM modul opcionális"],
            "ip_vedelem":       "IP20",
            "tapfeszultseg_V":  "17V AC / 12V DC",
            "kimenet_db":       8,
            "felhasznalok":     999,
            "memoriapontok":    1000,
            "buszos":           True,
            "alkalmazas":       ["nagyobb épület", "gyár", "intézmény"],
        },
        "nagyker_netto": 68500,
        "kisker_netto":  99000,
    },
    {
        "crt_code": "V-007",
        "name":     "Optex BX-80N kültéri PIR mozgásérzékelő",
        "unit":     "db",
        "cat":      "cat-riaszto",
        "model":    "BX-80N",
        "specs": {
            "gyarto":           "Optex",
            "technologia":      "PIR",
            "lefedes_szog":     "90°",
            "lefedes_tavolsag_m": 12,
            "ip_vedelem":       "IP55",
            "tapfeszultseg_V":  "10.5-16V DC",
            "homerseklet_C":    "-20 ~ +60",
            "tampervedelem":    True,
            "becsuszegetel":    False,
            "alkalmazas":       ["kültéri fal", "kapu mellé", "kerítés vonal"],
        },
        "nagyker_netto": 18800,
        "kisker_netto":  27500,
    },
    {
        "crt_code": "V-008",
        "name":     "Elmo BZX12 beltéri piezo sziréna",
        "unit":     "db",
        "cat":      "cat-riaszto",
        "model":    "BZX12",
        "specs": {
            "gyarto":           "Elmo",
            "hangerő_dB":       100,
            "tapfeszultseg_V":  "12V DC",
            "aram_ma":          400,
            "ip_vedelem":       "IP20",
            "szin":             "fehér",
            "tamper":           True,
            "alkalmazas":       ["beltéri riasztás jelzés", "folyosó", "lépcsőház"],
        },
        "nagyker_netto": 3250,
        "kisker_netto":  4900,
    },
    {
        "crt_code": "V-009",
        "name":     "Satel INT-TSH érintőképernyős LCD kezelő",
        "unit":     "db",
        "cat":      "cat-riaszto",
        "model":    "INT-TSH",
        "specs": {
            "gyarto":           "Satel",
            "kijelzo":          '4.3" TFT érintő',
            "felbontas_px":     "480×272",
            "kommunikacio":     ["Satel INTEGRA busz"],
            "tapfeszultseg_V":  "12V DC (buszról)",
            "ip_vedelem":       "IP20",
            "szin":             "fehér",
            "alkalmazas":       ["INTEGRA riasztóközpontokhoz", "recepció", "belépő"],
        },
        "nagyker_netto": 12800,
        "kisker_netto":  18900,
    },
    {
        "crt_code": "V-010",
        "name":     "Hikvision DS-2CD2347G2-LU 4MP ColorVu kamera",
        "unit":     "db",
        "cat":      "cat-kamera",
        "model":    "DS-2CD2347G2-LU",
        "specs": {
            "gyarto":           "Hikvision",
            "felbontas_MP":     4,
            "optika_mm":        4.0,
            "feher_feny_m":     40,
            "ip_vedelem":       "IP67",
            "taplaltas":        ["PoE (802.3af)", "12V DC"],
            "video_tomoritoo":  "H.265+",
            "szin_ejjel":       True,
            "sd_kartya":        "max 256GB",
            "mikrofon":         True,
            "ai_funkciok":      ["emberdetekció", "jármű detekció"],
            "alkalmazas":       ["színes éjszakai felvétel", "parkoló", "bejárat"],
        },
        "nagyker_netto": 19200,
        "kisker_netto":  28000,
    },
]


# ── SEED LOGIKA ──────────────────────────────────────────────────────────────

def run():
    print("CRT Cikktörzs seed v0.1")
    print("=" * 60)

    with engine.begin() as conn:

        # 1. Kategóriák
        print("\n[1/3] Kategóriák…")
        for cat in CATS:
            conn.execute(text("""
                INSERT INTO categories (category_id, parent_id, name, item_class, sort_order, active)
                VALUES (:id, :pid, :name, :cls, 0, true)
                ON CONFLICT (category_id) DO UPDATE
                SET name=EXCLUDED.name
            """), {"id": cat["id"], "pid": cat.get("parent"), "name": cat["name"], "cls": cat["class"]})
        print(f"   {len(CATS)} kategória OK")

        # 2. Termékek
        print("\n[2/3] Termékek…")
        import json as _json
        inserted = 0
        for p in PRODUCTS:
            iid = str(uuid.uuid4())
            conn.execute(text("""
                INSERT INTO products
                    (item_id, crt_code, model, category_id, name, unit, item_class,
                     specs, active, created_at)
                VALUES
                    (:iid, :code, :model, :cat, :name, :unit, 'materialis',
                     :specs::jsonb, true, :now)
                ON CONFLICT (crt_code) DO UPDATE
                SET name=EXCLUDED.name, specs=EXCLUDED.specs,
                    model=EXCLUDED.model, updated_at=:now
                RETURNING item_id
            """), {
                "iid":   iid,
                "code":  p["crt_code"],
                "model": p.get("model"),
                "cat":   p["cat"],
                "name":  p["name"],
                "unit":  p["unit"],
                "specs": _json.dumps(p["specs"], ensure_ascii=False),
                "now":   NOW,
            })
            inserted += 1

        print(f"   {inserted} termék OK")

        # 3. Árak — nettó nagyker + nettó kisker + bruttó mindkettő
        print("\n[3/3] Árak (nettó + bruttó × nagyker/kisker)…")
        price_rows = 0
        for p in PRODUCTS:
            # lekérjük az éppen beillesztett item_id-t crt_code alapján
            row = conn.execute(text(
                "SELECT item_id FROM products WHERE crt_code=:c"
            ), {"c": p["crt_code"]}).fetchone()
            if not row:
                continue
            iid = row[0]

            tiers = [
                ("nagyker", p["nagyker_netto"]),
                ("kisker",  p["kisker_netto"]),
            ]
            for tier, netto in tiers:
                brutto = round(netto * (1 + VAT / 100), 2)
                conn.execute(text("""
                    INSERT INTO prices
                        (price_id, item_id, item_class, price_type, price_tier,
                         net_price, gross_price, vat_pct, currency, db_inserted, source)
                    VALUES
                        (:pid, :iid, 'materialis', 'lista', :tier,
                         :netto, :brutto, :vat, 'HUF', :now, 'seed_v01')
                    ON CONFLICT DO NOTHING
                """), {
                    "pid":    str(uuid.uuid4()),
                    "iid":    iid,
                    "tier":   tier,
                    "netto":  netto,
                    "brutto": brutto,
                    "vat":    VAT,
                    "now":    NOW,
                })
                price_rows += 1

        print(f"   {price_rows} ársor OK  ({price_rows//2} termék × 2 szint)")

    # ── Összesítő / szűrő példák ─────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("ÖSSZESÍTŐ NÉZET\n")

    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT
                p.crt_code,
                p.name,
                p.unit,
                p.specs->>'kabel_tipus'          AS kabel_tipus,
                p.specs->>'keresztmetszet_mm2'   AS km2,
                p.specs->>'erek_szama'            AS erek,
                p.specs->>'amper_A'               AS amper,
                p.specs->>'karakterisztika'       AS karakt,
                p.specs->>'polus'                 AS polus,
                p.specs->>'nev_aram_A'            AS nev_aram,
                p.specs->>'megszakito_kep_kA'     AS megszkep,
                p.specs->>'ip_vedelem'            AS ip,
                p.specs->>'zonak_szama'           AS zonak,
                pr_nk.net_price                   AS nagyker_netto,
                pr_nk.gross_price                 AS nagyker_brutto,
                pr_kk.net_price                   AS kisker_netto,
                pr_kk.gross_price                 AS kisker_brutto
            FROM products p
            LEFT JOIN prices pr_nk ON pr_nk.item_id=p.item_id AND pr_nk.price_tier='nagyker'
            LEFT JOIN prices pr_kk ON pr_kk.item_id=p.item_id AND pr_kk.price_tier='kisker'
            ORDER BY p.crt_code
        """)).fetchall()

    print(f"{'KOD':<7} {'NEV':<45} {'EGYS':<4} "
          f"{'NK-NETTO':>9} {'NK-BRUTTO':>10} {'KK-NETTO':>9} {'KK-BRUTTO':>10}")
    print("-" * 100)
    for r in rows:
        print(f"{r[0]:<7} {r[1][:44]:<45} {r[2]:<4} "
              f"{r[13] or 0:>9,.0f} {r[14] or 0:>10,.0f} "
              f"{r[15] or 0:>9,.0f} {r[16] or 0:>10,.0f}")

    # Szűrő példák
    print(f"\n{'='*60}")
    print("SZŰRŐ: Csak kábelek ≥ 2,5 mm² keresztmetszettel")
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT crt_code, name, (specs->>'keresztmetszet_mm2')::numeric AS km2,
                   specs->>'amper_A' AS amper, specs->>'alkalmazas' AS alk
            FROM products
            WHERE specs->>'kabel_tipus' IS NOT NULL
              AND (specs->>'keresztmetszet_mm2')::numeric >= 2.5
            ORDER BY (specs->>'keresztmetszet_mm2')::numeric
        """)).fetchall()
    for r in rows:
        print(f"  {r[0]} | {r[1][:40]} | {r[2]} mm² | {r[3]}A")

    print(f"\nSZŰRŐ: Kismegszakítók C karakterisztika, ≥ 6kA megszakítóképesség")
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT crt_code, name,
                   specs->>'polus' AS polus,
                   specs->>'nev_aram_A' AS aram,
                   specs->>'megszakito_kep_kA' AS ka
            FROM products
            WHERE specs->>'karakterisztika' = 'C'
              AND (specs->>'megszakito_kep_kA')::numeric >= 6.0
            ORDER BY (specs->>'nev_aram_A')::numeric
        """)).fetchall()
    for r in rows:
        print(f"  {r[0]} | {r[1][:40]} | {r[2]} | {r[3]}A | {r[4]}kA")

    print(f"\nSZŰRŐ: Vagyonvédelmi kültéri (IP≥44)")
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT crt_code, name, specs->>'ip_vedelem' AS ip,
                   pr.net_price AS nagyker_netto
            FROM products p
            JOIN prices pr ON pr.item_id=p.item_id AND pr.price_tier='nagyker'
            WHERE specs->>'ip_vedelem' IN ('IP44','IP55','IP65','IP66','IP67','IP68')
            ORDER BY pr.net_price
        """)).fetchall()
    for r in rows:
        print(f"  {r[0]} | {r[1][:40]} | {r[2]} | {r[3]:,.0f} Ft nettó/nagyker")

    print("\nSeed kész.")


if __name__ == "__main__":
    run()
