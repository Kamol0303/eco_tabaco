"""SQLite ma'lumotlar bazasi va Ko'p bosqichli ECO boshqaruv tizimi (SuperAdmin, Dilerlar, Ombor, Moliya)."""
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

TZ = timezone(timedelta(hours=5))  # Toshkent vaqti (UTC+5)


def now_str() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")


UZB_REGIONS = [
    {
        "code": "tashkent_city",
        "name": "Toshkent shahri",
        "districts": ["Yunusobod", "Chilonzor", "Mirzo Ulug'bek", "Yakkasaroy", "Shayxontohur", "Mirobod", "Olmazor", "Sergeli", "Uchtepa", "Bektemir", "Yangihayot", "Yashnobod"],
    },
    {
        "code": "tashkent_region",
        "name": "Toshkent viloyati",
        "districts": ["Angren", "Bekobod sh.", "Bo'stonliq", "Bo'ka", "Chinoz", "Qibray", "Parkent", "Piskent", "O'rtachirchiq", "Yangiyo'l", "Zangiota", "Yuqorichirchiq", "Quyi Chirchiq", "Toshkent t.", "Ohangaron"],
    },
    {
        "code": "samarkand",
        "name": "Samarqand viloyati",
        "districts": ["Samarqand sh.", "Samarqand t.", "Bulung'ur", "Jomboy", "Ishtixon", "Kattaqo'rg'on sh.", "Kattaqo'rg'on t.", "Narpay", "Nurobod", "Oqdaryo", "Paxtachi", "Payariq", "Pastdarg'om", "Toyloq", "Urgut"],
    },
    {
        "code": "bukhara",
        "name": "Buxoro viloyati",
        "districts": ["Buxoro sh.", "Buxoro t.", "Vobkent", "G'ijduvon", "Jondor", "Kogon sh.", "Kogon t.", "Qorako'l", "Qorovulbozor", "Olot", "Peshku", "Romitan", "Shofirkon"],
    },
    {
        "code": "andijan",
        "name": "Andijon viloyati",
        "districts": ["Andijon sh.", "Andijon t.", "Asaka", "Baliqchi", "Bo'ston", "Buloqboshi", "Izboskan", "Jalaquduq", "Marhamat", "Oltinko'l", "Paxtaobod", "Shahrixon", "Ulug'nor", "Xo'jaobod", "Qo'rg'ontepa"],
    },
    {
        "code": "fergana",
        "name": "Farg'ona viloyati",
        "districts": ["Farg'ona sh.", "Bag'dod", "Beshariq", "Buvayda", "Dang'ara", "Farg'ona t.", "Furqat", "Oltiariq", "Qo'qon sh.", "Qoshtepa", "Quva", "Quvasoy sh.", "Rishton", "So'x", "Toshloq", "Uchko'prik", "O'zbekiston", "Yozyovon"],
    },
    {
        "code": "namangan",
        "name": "Namangan viloyati",
        "districts": ["Namangan sh.", "Chortoq", "Chust", "Kosonsoy", "Mingbuloq", "Namangan t.", "Norin", "Pop", "To'raqo'rg'on", "Uchqo'rg'on", "Uychi", "Yangiqo'rg'on"],
    },
    {
        "code": "kashkadarya",
        "name": "Qashqadaryo viloyati",
        "districts": ["Qarshi sh.", "Qarshi t.", "Chiroqchi", "Dehqonobod", "G'uzor", "Kasbi", "Kitob", "Ko'kdala", "Koson", "Mirishkor", "Muborak", "Nishon", "Qamashi", "Shahrisabz sh.", "Shahrisabz t.", "Yakkabog'"],
    },
    {
        "code": "surkhandarya",
        "name": "Surxondaryo viloyati",
        "districts": ["Termiz sh.", "Termiz t.", "Angor", "Bandixon", "Boysun", "Denov", "Jarqo'rg'on", "Muzrabot", "Oltinsoy", "Qiziriq", "Qumqo'rg'on", "Sariosiyo", "Sherobod", "Sho'rchi", "Uzun"],
    },
    {
        "code": "jizzakh",
        "name": "Jizzax viloyati",
        "districts": ["Jizzax sh.", "Arnasoy", "Baxmal", "Do'stlik", "Forish", "G'allaorol", "Sharof Rashidov", "Mirzacho'l", "Paxtakor", "Yangiobod", "Zomin", "Zafarobod", "Zarbdor"],
    },
    {
        "code": "sirdaryo",
        "name": "Sirdaryo viloyati",
        "districts": ["Guliston sh.", "Guliston t.", "Boyovut", "Mirzaobod", "Oqoltin", "Sardoba", "Sayxunobod", "Sirdaryo t.", "Xovos", "Shirin sh.", "Yangiyer sh."],
    },
    {
        "code": "navoiy",
        "name": "Navoiy viloyati",
        "districts": ["Navoiy sh.", "Zarafshon sh.", "Karmana", "Konimex", "Qiziltepa", "Xatirchi", "Navbahor", "Nurota", "Tomdi", "Uchquduq"],
    },
    {
        "code": "khorezm",
        "name": "Xorazm viloyati",
        "districts": ["Urganch sh.", "Urganch t.", "Bog'ot", "Gurlan", "Xiva sh.", "Xiva t.", "Xonqa", "Hazorasp", "Qo'shko'pir", "Shovot", "Yangiariq", "Yangibozor", "Tuproqqal'a"],
    },
    {
        "code": "karakalpakstan",
        "name": "Qoraqalpog'iston Respublikasi",
        "districts": ["Nukus sh.", "Amudaryo", "Beruniy", "Chimboy", "Ellikqala", "Kegeyli", "Mo'ynoq", "Nukus t.", "Qanliko'l", "Qo'ng'irot", "Qorao'zak", "Shumanay", "Taxtako'pir", "To'rtko'l", "Xo'jayli", "Bo'zatov", "Taxiatosh sh."],
    },
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    tg_id         INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    phone         TEXT,
    age_ok        INTEGER NOT NULL DEFAULT 0,
    region_id     INTEGER,
    district      TEXT,
    registered_at TEXT,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    key             TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    description     TEXT NOT NULL,
    price           INTEGER NOT NULL,
    cost_price      INTEGER NOT NULL DEFAULT 150000,
    wholesale_price INTEGER NOT NULL DEFAULT 190000,
    image           TEXT,
    file_id         TEXT,
    active          INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS cart (
    user_id    INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    qty        INTEGER NOT NULL,
    PRIMARY KEY (user_id, product_id),
    FOREIGN KEY (product_id) REFERENCES products(id)
);

CREATE TABLE IF NOT EXISTS regions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL UNIQUE,
    code           TEXT NOT NULL UNIQUE,
    districts_json TEXT NOT NULL,
    active         INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS dealers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    region_id       INTEGER NOT NULL UNIQUE REFERENCES regions(id),
    tg_id           INTEGER NOT NULL,
    name            TEXT NOT NULL,
    phone           TEXT,
    wholesale_model TEXT NOT NULL DEFAULT 'consignment',
    status          TEXT NOT NULL DEFAULT 'active',
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS factory_inventory (
    product_id INTEGER PRIMARY KEY REFERENCES products(id),
    stock      INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS dealer_inventory (
    dealer_id  INTEGER NOT NULL REFERENCES dealers(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    stock      INTEGER NOT NULL DEFAULT 0,
    reserved   INTEGER NOT NULL DEFAULT 0,
    sold       INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (dealer_id, product_id)
);

CREATE TABLE IF NOT EXISTS inventory_transactions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    target_type    TEXT NOT NULL,
    target_id      INTEGER,
    product_id     INTEGER NOT NULL REFERENCES products(id),
    change_qty     INTEGER NOT NULL,
    operation_type TEXT NOT NULL,
    ref_id         INTEGER,
    note           TEXT,
    created_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS shipments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tracking_no     TEXT NOT NULL UNIQUE,
    dealer_id       INTEGER NOT NULL REFERENCES dealers(id),
    region_id       INTEGER NOT NULL REFERENCES regions(id),
    status          TEXT NOT NULL DEFAULT 'pending',
    total_cost      INTEGER NOT NULL DEFAULT 0,
    total_wholesale INTEGER NOT NULL DEFAULT 0,
    notes           TEXT,
    shipped_at      TEXT,
    received_at     TEXT,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS shipment_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    shipment_id     INTEGER NOT NULL REFERENCES shipments(id),
    product_id      INTEGER NOT NULL REFERENCES products(id),
    sent_qty        INTEGER NOT NULL,
    received_qty    INTEGER NOT NULL DEFAULT 0,
    discrepancy_qty INTEGER NOT NULL DEFAULT 0,
    cost_price      INTEGER NOT NULL DEFAULT 0,
    unit_price      INTEGER NOT NULL DEFAULT 0,
    total_price     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS orders (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER NOT NULL,
    user_name      TEXT NOT NULL,
    phone          TEXT NOT NULL,
    region_id      INTEGER REFERENCES regions(id),
    district       TEXT,
    dealer_id      INTEGER REFERENCES dealers(id),
    total          INTEGER NOT NULL,
    lat            REAL NOT NULL,
    lon            REAL NOT NULL,
    status         TEXT NOT NULL DEFAULT 'new',
    payment_status TEXT NOT NULL DEFAULT 'unpaid',
    payment_method TEXT NOT NULL DEFAULT 'cash',
    paid_amount    INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS order_items (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id     INTEGER NOT NULL,
    product_name TEXT NOT NULL,
    price        INTEGER NOT NULL,
    qty          INTEGER NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(id)
);

CREATE TABLE IF NOT EXISTS dealer_finances (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    dealer_id      INTEGER NOT NULL REFERENCES dealers(id),
    operation_type TEXT NOT NULL,
    amount         INTEGER NOT NULL,
    payment_method TEXT DEFAULT 'cash',
    ref_id         INTEGER,
    note           TEXT,
    created_by     INTEGER,
    created_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id     INTEGER NOT NULL,
    action       TEXT NOT NULL,
    entity       TEXT NOT NULL,
    entity_id    INTEGER,
    details_json TEXT,
    created_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_orders_user    ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status  ON orders(status);
"""


class Database:
    def __init__(self, path: Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("PRAGMA cache_size=-64000")
        self.conn.execute("PRAGMA temp_store=MEMORY")
        self.conn.execute("PRAGMA mmap_size=268435456")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(SCHEMA)
        self._migrate()
        self._create_indexes()
        self._seed_regions()

    def _create_indexes(self) -> None:
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_dealer  ON orders(dealer_id)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_region  ON orders(region_id)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_dealers_tg     ON dealers(tg_id)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_shipments_dlr  ON shipments(dealer_id)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_shipments_st   ON shipments(status)")

    def _migrate(self) -> None:
        """Mavjud jadvallarga yangi ustunlarni xavfsiz qo'shadi."""
        def col_exists(table: str, col: str) -> bool:
            rows = self.conn.execute(f"PRAGMA table_info({table})").fetchall()
            return any(r["name"] == col for r in rows)

        # users jadvali
        if not col_exists("users", "region_id"):
            self.conn.execute("ALTER TABLE users ADD COLUMN region_id INTEGER REFERENCES regions(id)")
        if not col_exists("users", "district"):
            self.conn.execute("ALTER TABLE users ADD COLUMN district TEXT")

        # products jadvali
        if not col_exists("products", "cost_price"):
            self.conn.execute("ALTER TABLE products ADD COLUMN cost_price INTEGER NOT NULL DEFAULT 150000")
        if not col_exists("products", "wholesale_price"):
            self.conn.execute("ALTER TABLE products ADD COLUMN wholesale_price INTEGER NOT NULL DEFAULT 190000")

        # orders jadvali
        if not col_exists("orders", "region_id"):
            self.conn.execute("ALTER TABLE orders ADD COLUMN region_id INTEGER REFERENCES regions(id)")
        if not col_exists("orders", "district"):
            self.conn.execute("ALTER TABLE orders ADD COLUMN district TEXT")
        if not col_exists("orders", "dealer_id"):
            self.conn.execute("ALTER TABLE orders ADD COLUMN dealer_id INTEGER REFERENCES dealers(id)")
        if not col_exists("orders", "payment_status"):
            self.conn.execute("ALTER TABLE orders ADD COLUMN payment_status TEXT NOT NULL DEFAULT 'unpaid'")
        if not col_exists("orders", "payment_method"):
            self.conn.execute("ALTER TABLE orders ADD COLUMN payment_method TEXT NOT NULL DEFAULT 'cash'")
        if not col_exists("orders", "paid_amount"):
            self.conn.execute("ALTER TABLE orders ADD COLUMN paid_amount INTEGER NOT NULL DEFAULT 0")

    def _seed_regions(self) -> None:
        """O'zbekiston viloyatlari va tumanlarini bazaga kiritadi."""
        for r in UZB_REGIONS:
            self.conn.execute(
                "INSERT OR IGNORE INTO regions(name, code, districts_json, active) VALUES (?, ?, ?, 1)",
                (r["name"], r["code"], json.dumps(r["districts"], ensure_ascii=False)),
            )

    # ==================== HUDUDLAR VA DILERLAR ====================
    def get_regions(self, active_only: bool = True):
        sql = "SELECT * FROM regions"
        if active_only:
            sql += " WHERE active=1"
        return self.conn.execute(sql + " ORDER BY id").fetchall()

    def get_region(self, region_id: int):
        return self.conn.execute("SELECT * FROM regions WHERE id=?", (region_id,)).fetchone()

    def get_dealers(self):
        sql = """
            SELECT d.*, r.name AS region_name, r.code AS region_code
            FROM dealers d
            JOIN regions r ON r.id = d.region_id
            ORDER BY r.id
        """
        return self.conn.execute(sql).fetchall()

    def get_dealer(self, dealer_id: int):
        sql = """
            SELECT d.*, r.name AS region_name, r.code AS region_code
            FROM dealers d
            JOIN regions r ON r.id = d.region_id
            WHERE d.id=?
        """
        return self.conn.execute(sql, (dealer_id,)).fetchone()

    def get_dealer_by_tg_id(self, tg_id: int):
        sql = """
            SELECT d.*, r.name AS region_name, r.code AS region_code
            FROM dealers d
            JOIN regions r ON r.id = d.region_id
            WHERE d.tg_id=? AND d.status='active'
        """
        return self.conn.execute(sql, (tg_id,)).fetchone()

    def get_dealer_by_region(self, region_id: int):
        sql = """
            SELECT d.*, r.name AS region_name, r.code AS region_code
            FROM dealers d
            JOIN regions r ON r.id = d.region_id
            WHERE d.region_id=? AND d.status='active'
        """
        return self.conn.execute(sql, (region_id,)).fetchone()

    def upsert_dealer(
        self,
        region_id: int,
        tg_id: int,
        name: str,
        phone: str = "",
        wholesale_model: str = "consignment",
        status: str = "active",
        actor_id: int = 0,
    ) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO dealers(region_id, tg_id, name, phone, wholesale_model, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(region_id) DO UPDATE SET
                tg_id=excluded.tg_id,
                name=excluded.name,
                phone=excluded.phone,
                wholesale_model=excluded.wholesale_model,
                status=excluded.status
            """,
            (region_id, tg_id, name, phone, wholesale_model, status, now_str()),
        )
        dealer = self.get_dealer_by_region(region_id)
        did = dealer["id"] if dealer else cur.lastrowid
        self.log_audit(actor_id, "upsert_dealer", "dealers", did, {"region_id": region_id, "tg_id": tg_id, "status": status})
        return did

    def set_dealer_status(self, dealer_id: int, status: str, actor_id: int = 0) -> None:
        self.conn.execute("UPDATE dealers SET status=? WHERE id=?", (status, dealer_id))
        self.log_audit(actor_id, "set_dealer_status", "dealers", dealer_id, {"status": status})

    def delete_dealer(self, dealer_id: int, actor_id: int = 0) -> None:
        self.conn.execute("DELETE FROM dealers WHERE id=?", (dealer_id,))
        self.log_audit(actor_id, "delete_dealer", "dealers", dealer_id, {})

    # ==================== MAHSULOTLAR ====================
    def seed_products(self, products: list[tuple]) -> None:
        for key, name, desc, price, image in products:
            cost = int(price * 0.65)
            wholesale = int(price * 0.85)
            self.conn.execute(
                "INSERT OR IGNORE INTO products(key, name, description, price, cost_price, wholesale_price, image) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (key, name, desc, price, cost, wholesale, image),
            )
            # Zavod omboriga birlamchi tovar qoldig'i
            p = self.conn.execute("SELECT id FROM products WHERE key=?", (key,)).fetchone()
            if p:
                self.conn.execute(
                    "INSERT OR IGNORE INTO factory_inventory(product_id, stock) VALUES (?, 10000)",
                    (p["id"],),
                )

    def products(self, active_only: bool = True):
        sql = "SELECT * FROM products"
        if active_only:
            sql += " WHERE active=1"
        return self.conn.execute(sql + " ORDER BY id").fetchall()

    def get_product(self, pid: int):
        return self.conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()

    def create_product(self, key: str, name: str, description: str, price: int, cost_price: int, wholesale_price: int, image: str = "") -> int:
        cur = self.conn.execute(
            "INSERT INTO products(key, name, description, price, cost_price, wholesale_price, image) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (key, name, description, price, cost_price, wholesale_price, image),
        )
        pid = cur.lastrowid
        self.conn.execute("INSERT OR IGNORE INTO factory_inventory(product_id, stock) VALUES (?, 0)", (pid,))
        return pid

    def update_product(self, pid: int, name: str, description: str, price: int, cost_price: int, wholesale_price: int, active: int) -> bool:
        cur = self.conn.execute(
            "UPDATE products SET name=?, description=?, price=?, cost_price=?, wholesale_price=?, active=? WHERE id=?",
            (name, description, price, cost_price, wholesale_price, active, pid),
        )
        return cur.rowcount > 0

    def set_file_id(self, pid: int, file_id: str) -> None:
        self.conn.execute("UPDATE products SET file_id=? WHERE id=?", (file_id, pid))

    def set_price(self, key: str, price: int) -> bool:
        cur = self.conn.execute("UPDATE products SET price=? WHERE key=?", (price, key))
        return cur.rowcount > 0

    def set_price_by_id(self, pid: int, price: int) -> bool:
        cur = self.conn.execute("UPDATE products SET price=? WHERE id=?", (price, pid))
        return cur.rowcount > 0

    def toggle_product(self, pid: int) -> None:
        self.conn.execute("UPDATE products SET active = 1 - active WHERE id=?", (pid,))

    # ==================== FOYDALANUVCHILAR ====================
    def touch_user(self, tg_id: int, name: str) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO users(tg_id, name, created_at) VALUES (?, ?, ?)",
            (tg_id, name, now_str()),
        )

    def get_user(self, tg_id: int):
        return self.conn.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,)).fetchone()

    def is_registered(self, tg_id: int) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM users WHERE tg_id=? AND phone IS NOT NULL", (tg_id,)
        ).fetchone()
        return row is not None

    def set_age_ok(self, tg_id: int) -> None:
        self.conn.execute("UPDATE users SET age_ok=1 WHERE tg_id=?", (tg_id,))

    def register(self, tg_id: int, name: str, phone: str, region_id: int | None = None, district: str | None = None) -> None:
        self.touch_user(tg_id, name)
        self.conn.execute(
            "UPDATE users SET name=?, phone=?, region_id=COALESCE(?, region_id), district=COALESCE(?, district), registered_at=COALESCE(registered_at, ?) WHERE tg_id=?",
            (name, phone, region_id, district, now_str(), tg_id),
        )

    def set_user_region(self, tg_id: int, region_id: int, district: str) -> None:
        self.conn.execute(
            "UPDATE users SET region_id=?, district=? WHERE tg_id=?",
            (region_id, district, tg_id),
        )

    def users_list(self, limit: int = 50, region_id: int | None = None):
        sql = "SELECT u.*, r.name AS region_name FROM users u LEFT JOIN regions r ON r.id = u.region_id WHERE u.phone IS NOT NULL"
        args = []
        if region_id:
            sql += " AND u.region_id=?"
            args.append(region_id)
        sql += " ORDER BY u.registered_at DESC LIMIT ?"
        args.append(limit)
        return self.conn.execute(sql, tuple(args)).fetchall()

    def users_count(self, region_id: int | None = None) -> int:
        if region_id:
            return self.conn.execute("SELECT COUNT(*) FROM users WHERE phone IS NOT NULL AND region_id=?", (region_id,)).fetchone()[0]
        return self.conn.execute("SELECT COUNT(*) FROM users WHERE phone IS NOT NULL").fetchone()[0]

    # ==================== SAVATCHA ====================
    def cart_items(self, uid: int):
        return self.conn.execute(
            "SELECT p.id AS product_id, p.name, p.price, p.wholesale_price, p.cost_price, c.qty "
            "FROM cart c JOIN products p ON p.id = c.product_id "
            "WHERE c.user_id=? AND p.active=1 AND c.qty>0 ORDER BY p.id",
            (uid,),
        ).fetchall()

    def cart_qty(self, uid: int, pid: int) -> int:
        row = self.conn.execute(
            "SELECT qty FROM cart WHERE user_id=? AND product_id=?", (uid, pid)
        ).fetchone()
        return row["qty"] if row else 0

    def cart_set(self, uid: int, pid: int, qty: int) -> None:
        if qty <= 0:
            self.conn.execute("DELETE FROM cart WHERE user_id=? AND product_id=?", (uid, pid))
        else:
            self.conn.execute(
                "INSERT INTO cart(user_id, product_id, qty) VALUES (?, ?, ?) "
                "ON CONFLICT(user_id, product_id) DO UPDATE SET qty=excluded.qty",
                (uid, pid, qty),
            )

    def cart_clear(self, uid: int) -> None:
        self.conn.execute("DELETE FROM cart WHERE user_id=?", (uid,))

    # ==================== OMBOR (FACTORY & DEALER) ====================
    def get_factory_inventory(self):
        sql = """
            SELECT p.id AS product_id, p.key, p.name, p.price, p.cost_price, p.wholesale_price,
                   COALESCE(fi.stock, 0) AS factory_stock
            FROM products p
            LEFT JOIN factory_inventory fi ON fi.product_id = p.id
            ORDER BY p.id
        """
        return self.conn.execute(sql).fetchall()

    def adjust_factory_stock(self, product_id: int, change_qty: int, reason: str, actor_id: int = 0) -> int:
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            self.conn.execute(
                "INSERT INTO factory_inventory(product_id, stock) VALUES (?, ?) "
                "ON CONFLICT(product_id) DO UPDATE SET stock = stock + excluded.stock",
                (product_id, change_qty),
            )
            self.conn.execute(
                "INSERT INTO inventory_transactions(target_type, target_id, product_id, change_qty, operation_type, note, created_at) "
                "VALUES ('factory', NULL, ?, ?, 'manual_adjustment', ?, ?)",
                (product_id, change_qty, reason, now_str()),
            )
            self.conn.execute("COMMIT")
            row = self.conn.execute("SELECT stock FROM factory_inventory WHERE product_id=?", (product_id,)).fetchone()
            new_stock = row["stock"] if row else 0
            self.log_audit(actor_id, "adjust_factory_stock", "factory_inventory", product_id, {"change_qty": change_qty, "reason": reason, "new_stock": new_stock})
            return new_stock
        except Exception:
            self.conn.execute("ROLLBACK")
            raise

    def get_dealer_inventory(self, dealer_id: int):
        sql = """
            SELECT p.id AS product_id, p.key, p.name, p.price, p.wholesale_price, p.cost_price,
                   COALESCE(di.stock, 0) AS stock,
                   COALESCE(di.reserved, 0) AS reserved,
                   COALESCE(di.sold, 0) AS sold,
                   COALESCE(di.stock, 0) AS available,
                   (COALESCE(di.stock, 0) + COALESCE(di.reserved, 0)) AS total_physical
            FROM products p
            LEFT JOIN dealer_inventory di ON di.product_id = p.id AND di.dealer_id = ?
            WHERE p.active=1
            ORDER BY p.id
        """
        return self.conn.execute(sql, (dealer_id,)).fetchall()

    def check_dealer_stock(self, dealer_id: int, items: list[dict]) -> tuple[bool, str | None]:
        """Buyurtma berishdan oldin diler omboridagi qoldiqni tekshiradi."""
        for item in items:
            pid = item["product_id"]
            qty = item["qty"]
            row = self.conn.execute(
                "SELECT stock FROM dealer_inventory WHERE dealer_id=? AND product_id=?",
                (dealer_id, pid),
            ).fetchone()
            current_stock = row["stock"] if row else 0
            if current_stock < qty:
                p = self.get_product(pid)
                p_name = p["name"] if p else f"№{pid}"
                return False, f"«{p_name}» mahsulotidan omborda yetarli emas (qoldiq: {current_stock} ta, so'raldi: {qty} ta)."
        return True, None

    def adjust_dealer_stock(self, dealer_id: int, product_id: int, change_qty: int, reason: str, actor_id: int = 0) -> int:
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            self.conn.execute(
                "INSERT INTO dealer_inventory(dealer_id, product_id, stock, reserved, sold) VALUES (?, ?, ?, 0, 0) "
                "ON CONFLICT(dealer_id, product_id) DO UPDATE SET stock = stock + excluded.stock",
                (dealer_id, product_id, change_qty),
            )
            self.conn.execute(
                "INSERT INTO inventory_transactions(target_type, target_id, product_id, change_qty, operation_type, note, created_at) "
                "VALUES ('dealer', ?, ?, ?, 'manual_adjustment', ?, ?)",
                (dealer_id, product_id, change_qty, reason, now_str()),
            )
            self.conn.execute("COMMIT")
            row = self.conn.execute("SELECT stock FROM dealer_inventory WHERE dealer_id=? AND product_id=?", (dealer_id, product_id)).fetchone()
            new_stock = row["stock"] if row else 0
            self.log_audit(actor_id, "adjust_dealer_stock", "dealer_inventory", dealer_id, {"product_id": product_id, "change": change_qty, "new_stock": new_stock})
            return new_stock
        except Exception:
            self.conn.execute("ROLLBACK")
            raise

    # ==================== JO'NATMALAR (ZAVOD -> DILER) ====================
    def create_shipment(
        self,
        dealer_id: int,
        items: list[dict],
        notes: str = "",
        actor_id: int = 0,
    ) -> tuple[bool, str, int | None]:
        """SuperAdmin zavoddan dilerga tovar yuboradi."""
        dealer = self.get_dealer(dealer_id)
        if not dealer:
            return False, "Diler topilmadi.", None

        self.conn.execute("BEGIN IMMEDIATE")
        try:
            # Zavod omborini tekshirish
            total_cost = 0
            total_wholesale = 0
            for it in items:
                pid = it["product_id"]
                sent_qty = int(it["sent_qty"])
                if sent_qty <= 0:
                    continue
                frow = self.conn.execute("SELECT stock FROM factory_inventory WHERE product_id=?", (pid,)).fetchone()
                fstock = frow["stock"] if frow else 0
                if fstock < sent_qty:
                    p = self.get_product(pid)
                    pname = p["name"] if p else f"№{pid}"
                    self.conn.execute("ROLLBACK")
                    return False, f"Zavod omborida «{pname}» yetarli emas (mavjud: {fstock} ta).", None

            today_compact = now_str()[:10].replace("-", "")
            cnt_row = self.conn.execute("SELECT COUNT(*) AS c FROM shipments WHERE substr(created_at,1,10)=?", (now_str()[:10],)).fetchone()
            tracking_no = f"SHP-{today_compact}-{cnt_row['c'] + 1:03d}"

            cur = self.conn.execute(
                """
                INSERT INTO shipments(tracking_no, dealer_id, region_id, status, total_cost, total_wholesale, notes, shipped_at, created_at)
                VALUES (?, ?, ?, 'shipped', 0, 0, ?, ?, ?)
                """,
                (tracking_no, dealer_id, dealer["region_id"], notes, now_str(), now_str()),
            )
            shipment_id = cur.lastrowid

            for it in items:
                pid = it["product_id"]
                sent_qty = int(it["sent_qty"])
                if sent_qty <= 0:
                    continue
                prod = self.get_product(pid)
                unit_price = int(it.get("unit_price") or prod["wholesale_price"] or prod["price"])
                cost_price = int(prod["cost_price"] or 0)
                subtotal = unit_price * sent_qty

                total_cost += cost_price * sent_qty
                total_wholesale += subtotal

                self.conn.execute(
                    """
                    INSERT INTO shipment_items(shipment_id, product_id, sent_qty, received_qty, discrepancy_qty, cost_price, unit_price, total_price)
                    VALUES (?, ?, ?, 0, ?, ?, ?, ?)
                    """,
                    (shipment_id, pid, sent_qty, sent_qty, cost_price, unit_price, subtotal),
                )

                # Zavod omboridan chiqarish
                self.conn.execute(
                    "UPDATE factory_inventory SET stock = stock - ? WHERE product_id=?",
                    (sent_qty, pid),
                )
                self.conn.execute(
                    """
                    INSERT INTO inventory_transactions(target_type, target_id, product_id, change_qty, operation_type, ref_id, note, created_at)
                    VALUES ('factory', NULL, ?, ?, 'shipment_out', ?, ?, ?)
                    """,
                    (pid, -sent_qty, shipment_id, f"Jo'natma {tracking_no} -> {dealer['name']}", now_str()),
                )

            self.conn.execute(
                "UPDATE shipments SET total_cost=?, total_wholesale=? WHERE id=?",
                (total_cost, total_wholesale, shipment_id),
            )

            self.conn.execute("COMMIT")
            self.log_audit(actor_id, "create_shipment", "shipments", shipment_id, {"tracking_no": tracking_no, "dealer_id": dealer_id, "total_wholesale": total_wholesale})
            return True, tracking_no, shipment_id
        except Exception:
            self.conn.execute("ROLLBACK")
            raise

    def confirm_shipment_receipt(
        self,
        shipment_id: int,
        dealer_id: int,
        received_items: dict[int, int],  # {product_id: received_qty}
        notes: str = "",
        actor_id: int = 0,
    ) -> tuple[bool, str]:
        """Diler tovarni qabul qilganini tasdiqlaydi (tafovut bilan yoki to'liq)."""
        shipment = self.conn.execute("SELECT * FROM shipments WHERE id=?", (shipment_id,)).fetchone()
        if not shipment:
            return False, "Jo'natma topilmadi."
        if shipment["dealer_id"] != dealer_id:
            return False, "Bu jo'natma sizning hududingizga tegishli emas."
        if shipment["status"] in ("delivered", "partial", "cancelled"):
            return False, "Ushbu jo'natma allaqachon qabul qilingan yoki bekor bo'lgan."

        s_items = self.conn.execute("SELECT * FROM shipment_items WHERE shipment_id=?", (shipment_id,)).fetchall()
        dealer = self.get_dealer(dealer_id)

        self.conn.execute("BEGIN IMMEDIATE")
        try:
            has_discrepancy = False
            total_received_wholesale = 0

            for item in s_items:
                pid = item["product_id"]
                sent_qty = item["sent_qty"]
                rec_qty = int(received_items.get(pid, sent_qty))
                if rec_qty < 0:
                    rec_qty = 0
                discrepancy = sent_qty - rec_qty
                if discrepancy != 0:
                    has_discrepancy = True

                subtotal = rec_qty * item["unit_price"]
                total_received_wholesale += subtotal

                self.conn.execute(
                    """
                    UPDATE shipment_items
                    SET received_qty=?, discrepancy_qty=?, total_price=?
                    WHERE id=?
                    """,
                    (rec_qty, discrepancy, subtotal, item["id"]),
                )

                # Diler virtual omboriga kirim
                self.conn.execute(
                    """
                    INSERT INTO dealer_inventory(dealer_id, product_id, stock, reserved, sold)
                    VALUES (?, ?, ?, 0, 0)
                    ON CONFLICT(dealer_id, product_id) DO UPDATE SET stock = stock + excluded.stock
                    """,
                    (dealer_id, pid, rec_qty),
                )
                self.conn.execute(
                    """
                    INSERT INTO inventory_transactions(target_type, target_id, product_id, change_qty, operation_type, ref_id, note, created_at)
                    VALUES ('dealer', ?, ?, ?, 'shipment_in', ?, ?, ?)
                    """,
                    (dealer_id, pid, rec_qty, shipment_id, f"Jo'natma qabuli: {shipment['tracking_no']}", now_str()),
                )

            final_status = "partial" if has_discrepancy else "delivered"
            self.conn.execute(
                "UPDATE shipments SET status=?, received_at=?, total_wholesale=?, notes=COALESCE(notes, '') || ? WHERE id=?",
                (final_status, now_str(), total_received_wholesale, f" [Qabul izohi: {notes}]" if notes else "", shipment_id),
            )

            # Dilerning hisob-kitobiga kirim summasini qarz sifatida yozish
            # Agar 'wholesale' modeli bo'lsa diler qabul qilgan tovar qiymati qarz bo'ladi
            # Agar 'consignment' (realizatsiya) bo'lsa, tovar berilgan, lekin sotilgach hisoblanadi. Biz ikkalasida ham kirim qiymatini hisoblaymiz.
            self.conn.execute(
                """
                INSERT INTO dealer_finances(dealer_id, operation_type, amount, ref_id, note, created_by, created_at)
                VALUES (?, 'shipment_charge', ?, ?, ?, ?, ?)
                """,
                (dealer_id, total_received_wholesale, shipment_id, f"Jo'natma №{shipment['tracking_no']} qabul qilindi", actor_id or dealer["tg_id"], now_str()),
            )

            self.conn.execute("COMMIT")
            self.log_audit(actor_id, "confirm_shipment_receipt", "shipments", shipment_id, {"status": final_status, "has_discrepancy": has_discrepancy})
            return True, "delivered" if not has_discrepancy else "partial"
        except Exception:
            self.conn.execute("ROLLBACK")
            raise

    def list_shipments(self, dealer_id: int | None = None, status: str | None = None, limit: int = 50):
        where, args = [], []
        if dealer_id:
            where.append("s.dealer_id=?")
            args.append(dealer_id)
        if status and status != "all":
            where.append("s.status=?")
            args.append(status)

        sql = """
            SELECT s.*, d.name AS dealer_name, r.name AS region_name
            FROM shipments s
            JOIN dealers d ON d.id = s.dealer_id
            JOIN regions r ON r.id = s.region_id
        """
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY s.id DESC LIMIT ?"
        args.append(limit)
        return self.conn.execute(sql, tuple(args)).fetchall()

    def get_shipment(self, shipment_id: int):
        sql = """
            SELECT s.*, d.name AS dealer_name, d.phone AS dealer_phone, r.name AS region_name
            FROM shipments s
            JOIN dealers d ON d.id = s.dealer_id
            JOIN regions r ON r.id = s.region_id
            WHERE s.id=?
        """
        return self.conn.execute(sql, (shipment_id,)).fetchone()

    def get_shipment_items(self, shipment_id: int):
        sql = """
            SELECT si.*, p.name AS product_name, p.key AS product_key
            FROM shipment_items si
            JOIN products p ON p.id = si.product_id
            WHERE si.shipment_id=?
            ORDER BY si.id
        """
        return self.conn.execute(sql, (shipment_id,)).fetchall()

    # ==================== BUYURTMALAR (HUDUD VA DILER BILAN) ====================
    def create_order(
        self,
        uid: int,
        lat: float,
        lon: float,
        expected_total: int,
        region_id: int | None = None,
        district: str | None = None,
        payment_method: str = "cash",
    ) -> tuple[str, int | None, int | None]:
        """Buyurtmani bitta tranzaksiyada yaratadi, hudud dilerini aniqlaydi va ombor qoldig'ini band qiladi."""
        user = self.get_user(uid)
        if not user or not user["phone"]:
            return "empty", None, None

        # Foydalanuvchi hududi
        final_region_id = region_id or user["region_id"]
        final_district = district or user["district"] or ""

        # Hududiy diler
        dealer = self.get_dealer_by_region(final_region_id) if final_region_id else None
        dealer_id = dealer["id"] if dealer else None

        self.conn.execute("BEGIN IMMEDIATE")
        try:
            items = self.cart_items(uid)
            if not items:
                self.conn.execute("ROLLBACK")
                return "empty", None, None

            total = sum(i["price"] * i["qty"] for i in items)
            if total != expected_total:
                self.conn.execute("ROLLBACK")
                return "changed", None, None

            # Diler omborini tekshirish (agar diler mavjud bo'lsa)
            if dealer_id:
                for it in items:
                    pid = it["product_id"]
                    qty = it["qty"]
                    d_inv = self.conn.execute(
                        "SELECT stock FROM dealer_inventory WHERE dealer_id=? AND product_id=?",
                        (dealer_id, pid),
                    ).fetchone()
                    avail = d_inv["stock"] if d_inv else 0
                    if avail < qty:
                        self.conn.execute("ROLLBACK")
                        return "out_of_stock", None, None

            order_status = "new" if dealer_id else "new_unassigned"
            cur = self.conn.execute(
                """
                INSERT INTO orders(user_id, user_name, phone, region_id, district, dealer_id, total, lat, lon, status, payment_status, payment_method, paid_amount, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'unpaid', ?, 0, ?)
                """,
                (uid, user["name"], user["phone"], final_region_id, final_district, dealer_id, total, lat, lon, order_status, payment_method, now_str()),
            )
            oid = cur.lastrowid

            for it in items:
                pid = it["product_id"]
                qty = it["qty"]
                self.conn.execute(
                    "INSERT INTO order_items(order_id, product_name, price, qty) VALUES (?, ?, ?, ?)",
                    (oid, it["name"], it["price"], qty),
                )

                # Diler omborida tovar band qilish (reserve)
                if dealer_id:
                    self.conn.execute(
                        """
                        UPDATE dealer_inventory
                        SET stock = stock - ?, reserved = reserved + ?
                        WHERE dealer_id=? AND product_id=?
                        """,
                        (qty, qty, dealer_id, pid),
                    )
                    self.conn.execute(
                        """
                        INSERT INTO inventory_transactions(target_type, target_id, product_id, change_qty, operation_type, ref_id, note, created_at)
                        VALUES ('dealer', ?, ?, ?, 'order_reserve', ?, ?, ?)
                        """,
                        (dealer_id, pid, -qty, oid, f"Buyurtma №{oid} uchun band qilindi", now_str()),
                    )

            self.conn.execute("DELETE FROM cart WHERE user_id=?", (uid,))
            self.conn.execute("COMMIT")
            return "ok", oid, dealer_id
        except Exception:
            self.conn.execute("ROLLBACK")
            raise

    def get_order(self, oid: int):
        sql = """
            SELECT o.*, r.name AS region_name, d.name AS dealer_name, d.phone AS dealer_phone
            FROM orders o
            LEFT JOIN regions r ON r.id = o.region_id
            LEFT JOIN dealers d ON d.id = o.dealer_id
            WHERE o.id=?
        """
        return self.conn.execute(sql, (oid,)).fetchone()

    def order_items(self, oid: int):
        return self.conn.execute("SELECT * FROM order_items WHERE order_id=? ORDER BY id", (oid,)).fetchall()

    def list_orders(
        self,
        status: str | None = None,
        user_id: int | None = None,
        dealer_id: int | None = None,
        region_id: int | None = None,
        limit: int = 50,
    ):
        where, args = [], []
        if status and status != "all":
            where.append("o.status=?")
            args.append(status)
        if user_id:
            where.append("o.user_id=?")
            args.append(user_id)
        if dealer_id:
            where.append("o.dealer_id=?")
            args.append(dealer_id)
        if region_id:
            where.append("o.region_id=?")
            args.append(region_id)

        sql = """
            SELECT o.*, r.name AS region_name, d.name AS dealer_name
            FROM orders o
            LEFT JOIN regions r ON r.id = o.region_id
            LEFT JOIN dealers d ON d.id = o.dealer_id
        """
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY o.id DESC LIMIT ?"
        args.append(limit)
        return self.conn.execute(sql, tuple(args)).fetchall()

    def search_orders(self, q: str, dealer_id: int | None = None, limit: int = 50):
        like = f"%{q}%"
        oid = int(q) if q.isdigit() and len(q) <= 9 else -1
        where = ["(o.id=? OR o.phone LIKE ? OR o.user_name LIKE ? OR o.district LIKE ?)"]
        args = [oid, like, like, like]
        if dealer_id:
            where.append("o.dealer_id=?")
            args.append(dealer_id)

        sql = f"""
            SELECT o.*, r.name AS region_name, d.name AS dealer_name
            FROM orders o
            LEFT JOIN regions r ON r.id = o.region_id
            LEFT JOIN dealers d ON d.id = o.dealer_id
            WHERE {' AND '.join(where)}
            ORDER BY o.id DESC LIMIT ?
        """
        args.append(limit)
        return self.conn.execute(sql, tuple(args)).fetchall()

    def set_status(self, oid: int, status: str, actor_id: int = 0) -> None:
        """Buyurtma holatini yangilaydi va ombor hisobini to'g'ri o'zgartiradi."""
        order = self.conn.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
        if not order:
            return

        old_status = order["status"]
        if old_status == status:
            return

        dealer_id = order["dealer_id"]
        items = self.order_items(oid)

        self.conn.execute("BEGIN IMMEDIATE")
        try:
            self.conn.execute("UPDATE orders SET status=? WHERE id=?", (status, oid))

            # Agar buyurtma yakunlansa ('done'):
            if status == "done" and dealer_id:
                for it in items:
                    p = self.conn.execute("SELECT id FROM products WHERE name=?", (it["product_name"],)).fetchone()
                    if p:
                        pid = p["id"]
                        qty = it["qty"]
                        self.conn.execute(
                            "UPDATE dealer_inventory SET reserved = max(0, reserved - ?), sold = sold + ? WHERE dealer_id=? AND product_id=?",
                            (qty, qty, dealer_id, pid),
                        )
                        self.conn.execute(
                            """
                            INSERT INTO inventory_transactions(target_type, target_id, product_id, change_qty, operation_type, ref_id, note, created_at)
                            VALUES ('dealer', ?, ?, ?, 'order_sale', ?, ?, ?)
                            """,
                            (dealer_id, pid, qty, oid, f"Buyurtma №{oid} muvaffaqiyatli yakunlandi", now_str()),
                        )

            # Agar buyurtma bekor qilinsa ('cancelled'):
            elif status == "cancelled" and dealer_id:
                # Ilgari 'done' bo'lmagan bo'lsa, band qilingan tovar yana mavjud qoldiqqa qaytadi
                if old_status != "done":
                    for it in items:
                        p = self.conn.execute("SELECT id FROM products WHERE name=?", (it["product_name"],)).fetchone()
                        if p:
                            pid = p["id"]
                            qty = it["qty"]
                            self.conn.execute(
                                "UPDATE dealer_inventory SET reserved = max(0, reserved - ?), stock = stock + ? WHERE dealer_id=? AND product_id=?",
                                (qty, qty, dealer_id, pid),
                            )
                            self.conn.execute(
                                """
                                INSERT INTO inventory_transactions(target_type, target_id, product_id, change_qty, operation_type, ref_id, note, created_at)
                                VALUES ('dealer', ?, ?, ?, 'order_cancel_return', ?, ?, ?)
                                """,
                                (dealer_id, pid, qty, oid, f"Buyurtma №{oid} bekor qilinishi sababli qaytarildi", now_str()),
                            )

            # Agar tovar qaytarilsa ('returned'):
            elif status == "returned" and dealer_id:
                for it in items:
                    p = self.conn.execute("SELECT id FROM products WHERE name=?", (it["product_name"],)).fetchone()
                    if p:
                        pid = p["id"]
                        qty = it["qty"]
                        self.conn.execute(
                            "UPDATE dealer_inventory SET sold = max(0, sold - ?), stock = stock + ? WHERE dealer_id=? AND product_id=?",
                            (qty, qty, dealer_id, pid),
                        )
                        self.conn.execute(
                            """
                            INSERT INTO inventory_transactions(target_type, target_id, product_id, change_qty, operation_type, ref_id, note, created_at)
                            VALUES ('dealer', ?, ?, ?, 'order_return', ?, ?, ?)
                            """,
                            (dealer_id, pid, qty, oid, f"Buyurtma №{oid} mijoz tomonidan qaytarildi", now_str()),
                        )

            self.conn.execute("COMMIT")
            self.log_audit(actor_id, "set_order_status", "orders", oid, {"old_status": old_status, "new_status": status})
        except Exception:
            self.conn.execute("ROLLBACK")
            raise

    def set_order_payment(self, oid: int, payment_status: str, paid_amount: int, payment_method: str = "cash", actor_id: int = 0) -> None:
        self.conn.execute(
            "UPDATE orders SET payment_status=?, paid_amount=?, payment_method=? WHERE id=?",
            (payment_status, paid_amount, payment_method, oid),
        )
        self.log_audit(actor_id, "set_order_payment", "orders", oid, {"status": payment_status, "paid": paid_amount, "method": payment_method})

    # ==================== MOLIYA VA HISOBOTLAR ====================
    def record_dealer_payment(self, dealer_id: int, amount: int, payment_method: str, note: str = "", actor_id: int = 0) -> int:
        """Diler zavodga pul to'laganda qayd qilish (qarzdorlik kamayadi)."""
        cur = self.conn.execute(
            """
            INSERT INTO dealer_finances(dealer_id, operation_type, amount, payment_method, note, created_by, created_at)
            VALUES (?, 'payment', ?, ?, ?, ?, ?)
            """,
            (dealer_id, -abs(amount), payment_method, note, actor_id, now_str()),
        )
        fid = cur.lastrowid
        self.log_audit(actor_id, "record_dealer_payment", "dealer_finances", fid, {"dealer_id": dealer_id, "amount": amount, "method": payment_method})
        return fid

    def get_dealer_finance_summary(self, dealer_id: int) -> dict:
        """Dilerning zavod bilan moliyaviy hisobi va o'z savdo ko'rsatkichlari."""
        dealer = self.get_dealer(dealer_id)
        if not dealer:
            return {}

        today = now_str()[:10]
        month = today[:7]

        # 1. Zavoddan kelgan tovarlar umumiy qiymati
        shipped_val = self.conn.execute(
            "SELECT COALESCE(SUM(total_wholesale), 0) FROM shipments WHERE dealer_id=? AND status IN ('delivered', 'partial')",
            (dealer_id,),
        ).fetchone()[0]

        # 2. Zavodga to'langan pullar
        paid_val = self.conn.execute(
            "SELECT COALESCE(SUM(-amount), 0) FROM dealer_finances WHERE dealer_id=? AND operation_type='payment'",
            (dealer_id,),
        ).fetchone()[0]

        # 3. Zavod oldidagi qarz (Olingan tovar - to'langan pul)
        balance = self.conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM dealer_finances WHERE dealer_id=?",
            (dealer_id,),
        ).fetchone()[0]

        # 4. Dilerning mijozlarga sotuv statistikasi
        def sale_stats(where_clause: str, arg: tuple):
            sql = f"""
                SELECT COUNT(*) AS cnt,
                       COALESCE(SUM(total), 0) AS rev,
                       COALESCE(SUM(CASE WHEN payment_method='cash' THEN total ELSE 0 END), 0) AS cash,
                       COALESCE(SUM(CASE WHEN payment_method='card' THEN total ELSE 0 END), 0) AS card,
                       COALESCE(SUM(CASE WHEN payment_method='bank_transfer' THEN total ELSE 0 END), 0) AS transfer,
                       COALESCE(SUM(CASE WHEN payment_status='unpaid' THEN total ELSE 0 END), 0) AS unpaid
                FROM orders
                WHERE dealer_id=? AND status='done' {where_clause}
            """
            r = self.conn.execute(sql, (dealer_id, *arg)).fetchone()
            return {
                "orders_count": r["cnt"],
                "revenue": r["rev"],
                "cash": r["cash"],
                "card": r["card"],
                "transfer": r["transfer"],
                "unpaid": r["unpaid"],
            }

        return {
            "dealer_id": dealer_id,
            "dealer_name": dealer["name"],
            "region_name": dealer["region_name"],
            "wholesale_model": dealer["wholesale_model"],
            "shipped_goods_value": shipped_val,
            "payments_to_factory": paid_val,
            "current_debt": max(0, balance),
            "sales_today": sale_stats("AND substr(created_at,1,10)=?", (today,)),
            "sales_month": sale_stats("AND substr(created_at,1,7)=?", (month,)),
            "sales_total": sale_stats("", ()),
        }

    def get_dealer_ledger(self, dealer_id: int, limit: int = 50):
        sql = """
            SELECT df.*, u.name AS author_name
            FROM dealer_finances df
            LEFT JOIN users u ON u.tg_id = df.created_by
            WHERE df.dealer_id=?
            ORDER BY df.id DESC LIMIT ?
        """
        return self.conn.execute(sql, (dealer_id, limit)).fetchall()

    def superadmin_analytics(
        self,
        date_from: str | None = None,
        date_to: str | None = None,
        region_id: int | None = None,
    ) -> dict:
        """SuperAdmin uchun zavod va barcha dilerlar bo'yicha to'liq tahliliy hisobot."""
        now = now_str()
        today = now[:10]
        month = now[:7]
        year = now[:4]

        # 1. Savdo aylanmasi davrlar bo'yicha
        def period_sales(where_date: str, args: tuple):
            reg_filter = "AND region_id=?" if region_id else ""
            reg_args = (region_id,) if region_id else ()
            sql = f"""
                SELECT COUNT(*) AS c,
                       COALESCE(SUM(total), 0) AS rev
                FROM orders
                WHERE status='done' {where_date} {reg_filter}
            """
            r = self.conn.execute(sql, (*args, *reg_args)).fetchone()
            return r["c"], r["rev"]

        today_c, today_s = period_sales("AND substr(created_at,1,10)=?", (today,))
        month_c, month_s = period_sales("AND substr(created_at,1,7)=?", (month,))
        year_c, year_s = period_sales("AND substr(created_at,1,4)=?", (year,))
        total_c, total_s = period_sales("", ())

        # 2. Zavoddan dilerlarga yuborilgan tovarlar qiymati
        shipped_total = self.conn.execute(
            "SELECT COALESCE(SUM(total_wholesale), 0) FROM shipments WHERE status IN ('delivered', 'partial')"
        ).fetchone()[0]

        # 3. Dilerlardan kelib tushgan to'lovlar
        payments_total = self.conn.execute(
            "SELECT COALESCE(SUM(-amount), 0) FROM dealer_finances WHERE operation_type='payment'"
        ).fetchone()[0]

        # 4. Dilerlarning umumiy qarzdorligi
        total_debt = self.conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM dealer_finances"
        ).fetchone()[0]

        # 5. Yalpi foyda (Sotuv narxi - Tannarx)
        profit_row = self.conn.execute(
            """
            SELECT COALESCE(SUM(oi.price * oi.qty), 0) AS total_sale,
                   COALESCE(SUM(p.cost_price * oi.qty), 0) AS total_cost
            FROM order_items oi
            JOIN orders o ON o.id = oi.order_id
            JOIN products p ON p.name = oi.product_name
            WHERE o.status='done'
            """
        ).fetchone()
        gross_profit = (profit_row["total_sale"] - profit_row["total_cost"]) if profit_row else 0

        # 6. Hududlar bo'yicha solishtirma jadvali (14 ta hudud)
        regions_report = []
        for reg in self.get_regions(active_only=False):
            rid = reg["id"]
            dealer = self.get_dealer_by_region(rid)
            did = dealer["id"] if dealer else None

            # Diler ombor qoldig'i
            stock_sum = 0
            if did:
                srow = self.conn.execute(
                    "SELECT COALESCE(SUM(stock), 0) AS st FROM dealer_inventory WHERE dealer_id=?",
                    (did,),
                ).fetchone()
                stock_sum = srow["st"] if srow else 0

            # Hududdagi jami sotuv
            sale_row = self.conn.execute(
                "SELECT COUNT(*) AS c, COALESCE(SUM(total), 0) AS rev FROM orders WHERE region_id=? AND status='done'",
                (rid,),
            ).fetchone()

            # Qarz
            d_debt = 0
            if did:
                debt_row = self.conn.execute(
                    "SELECT COALESCE(SUM(amount), 0) AS b FROM dealer_finances WHERE dealer_id=?",
                    (did,),
                ).fetchone()
                d_debt = max(0, debt_row["b"] if debt_row else 0)

            regions_report.append({
                "region_id": rid,
                "region_name": reg["name"],
                "dealer_id": did,
                "dealer_name": dealer["name"] if dealer else "Biriktirilmagan",
                "dealer_phone": dealer["phone"] if dealer else "-",
                "status": dealer["status"] if dealer else "no_dealer",
                "current_stock": stock_sum,
                "orders_count": sale_row["c"] if sale_row else 0,
                "sales_revenue": sale_row["rev"] if sale_row else 0,
                "debt": d_debt,
            })

        # 7. Eng ko'p va eng kam sotilgan mahsulotlar
        products_ranking = self.conn.execute(
            """
            SELECT oi.product_name,
                   COALESCE(SUM(oi.qty), 0) AS total_sold,
                   COALESCE(SUM(oi.price * oi.qty), 0) AS total_revenue
            FROM order_items oi
            JOIN orders o ON o.id = oi.order_id
            WHERE o.status='done'
            GROUP BY oi.product_name
            ORDER BY total_sold DESC
            """
        ).fetchall()

        return {
            "today": {"count": today_c, "revenue": today_s},
            "month": {"count": month_c, "revenue": month_s},
            "year": {"count": year_c, "revenue": year_s},
            "total": {"count": total_c, "revenue": total_s},
            "shipped_goods_value": shipped_total,
            "payments_received": payments_total,
            "total_dealer_debt": max(0, total_debt),
            "gross_profit": gross_profit,
            "regions_report": regions_report,
            "products_ranking": [
                {"name": r["product_name"], "sold_qty": r["total_sold"], "revenue": r["total_revenue"]}
                for r in products_ranking
            ],
        }

    # ==================== AUDIT JURNALI ====================
    def log_audit(self, actor_id: int, action: str, entity: str, entity_id: int | None, details: dict) -> None:
        try:
            self.conn.execute(
                "INSERT INTO audit_log(actor_id, action, entity, entity_id, details_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (actor_id, action, entity, entity_id, json.dumps(details, ensure_ascii=False), now_str()),
            )
        except Exception:
            pass

    def get_audit_logs(self, limit: int = 50):
        sql = """
            SELECT a.*, u.name AS actor_name
            FROM audit_log a
            LEFT JOIN users u ON u.tg_id = a.actor_id
            ORDER BY a.id DESC LIMIT ?
        """
        return self.conn.execute(sql, (limit,)).fetchall()

    # ==================== STATISTIKA VA ZAXIRA ====================
    def stats(self) -> dict:
        today = now_str()[:10]
        month = today[:7]

        def agg(where: str, arg: str | None):
            sql = (
                "SELECT COUNT(*) AS c, "
                "COALESCE(SUM(CASE WHEN status NOT IN ('cancelled', 'returned') THEN total END), 0) AS s FROM orders "
                + where
            )
            row = self.conn.execute(sql, (arg,) if arg else ()).fetchone()
            return row["c"], row["s"]

        by_status = {
            r["status"]: r["c"]
            for r in self.conn.execute("SELECT status, COUNT(*) AS c FROM orders GROUP BY status")
        }
        return {
            "today": agg("WHERE substr(created_at,1,10)=?", today),
            "month": agg("WHERE substr(created_at,1,7)=?", month),
            "total": agg("", None),
            "by_status": by_status,
            "users": self.users_count(),
        }

    def backup(self, dst: Path) -> None:
        dst = Path(dst)
        dst.parent.mkdir(parents=True, exist_ok=True)
        target = sqlite3.connect(str(dst))
        try:
            self.conn.backup(target)
        finally:
            target.close()
