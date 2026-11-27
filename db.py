"""SQLite ma'lumotlar bazasi. Barcha so'rovlar parametrlangan (SQL injection'dan himoya)."""
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

TZ = timezone(timedelta(hours=5))  # Toshkent vaqti (UTC+5)


def now_str() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    tg_id         INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    phone         TEXT,
    age_ok        INTEGER NOT NULL DEFAULT 0,
    registered_at TEXT,
    created_at    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    key         TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    description TEXT NOT NULL,
    price       INTEGER NOT NULL,
    image       TEXT,
    file_id     TEXT,
    active      INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS cart (
    user_id    INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    qty        INTEGER NOT NULL,
    PRIMARY KEY (user_id, product_id),
    FOREIGN KEY (product_id) REFERENCES products(id)
);
CREATE TABLE IF NOT EXISTS orders (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    user_name  TEXT NOT NULL,
    phone      TEXT NOT NULL,
    total      INTEGER NOT NULL,
    lat        REAL NOT NULL,
    lon        REAL NOT NULL,
    status     TEXT NOT NULL DEFAULT 'new',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS order_items (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id     INTEGER NOT NULL,
    product_name TEXT NOT NULL,
    price        INTEGER NOT NULL,
    qty          INTEGER NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(id)
);
CREATE INDEX IF NOT EXISTS idx_orders_user   ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_date   ON orders(created_at);
"""


class Database:
    def __init__(self, path: Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), isolation_level=None)  # autocommit
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(SCHEMA)

    # ---------- mahsulotlar ----------
    def seed_products(self, products: list[tuple]) -> None:
        """products: (key, name, description, price, image). Mavjud bo'lsa o'zgartirmaydi."""
        for key, name, desc, price, image in products:
            self.conn.execute(
                "INSERT OR IGNORE INTO products(key, name, description, price, image) "
                "VALUES (?, ?, ?, ?, ?)",
                (key, name, desc, price, image),
            )

    def products(self, active_only: bool = True):
        sql = "SELECT * FROM products"
        if active_only:
            sql += " WHERE active=1"
        return self.conn.execute(sql + " ORDER BY id").fetchall()

    def get_product(self, pid: int):
        return self.conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()

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

    # ---------- foydalanuvchilar ----------
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

    def register(self, tg_id: int, name: str, phone: str) -> None:
        self.conn.execute(
            "UPDATE users SET name=?, phone=?, registered_at=COALESCE(registered_at, ?) WHERE tg_id=?",
            (name, phone, now_str(), tg_id),
        )

    def users_list(self, limit: int = 20):
        return self.conn.execute(
            "SELECT * FROM users WHERE phone IS NOT NULL ORDER BY registered_at DESC LIMIT ?",
            (limit,),
        ).fetchall()

    def users_count(self) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) FROM users WHERE phone IS NOT NULL"
        ).fetchone()[0]

    # ---------- savatcha (bazada saqlanadi, bot yopilsa ham yo'qolmaydi) ----------
    def cart_items(self, uid: int):
        return self.conn.execute(
            "SELECT p.id AS product_id, p.name, p.price, c.qty "
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

    # ---------- buyurtmalar ----------
    def create_order(self, uid: int, lat: float, lon: float, expected_total: int):
        """Buyurtmani bitta tranzaksiyada yaratadi va savatchani tozalaydi.

        Qaytaradi: ("ok", order_id) | ("empty", None) | ("changed", None)
        Takroriy bosishda savatcha bo'sh bo'ladi -> ikkinchi buyurtma yaratilmaydi.
        """
        user = self.get_user(uid)
        if not user or not user["phone"]:
            return "empty", None
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            items = self.cart_items(uid)
            if not items:
                self.conn.execute("ROLLBACK")
                return "empty", None
            total = sum(i["price"] * i["qty"] for i in items)
            if total != expected_total:
                self.conn.execute("ROLLBACK")
                return "changed", None
            cur = self.conn.execute(
                "INSERT INTO orders(user_id, user_name, phone, total, lat, lon, status, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 'new', ?)",
                (uid, user["name"], user["phone"], total, lat, lon, now_str()),
            )
            oid = cur.lastrowid
            self.conn.executemany(
                "INSERT INTO order_items(order_id, product_name, price, qty) VALUES (?, ?, ?, ?)",
                [(oid, i["name"], i["price"], i["qty"]) for i in items],
            )
            self.conn.execute("DELETE FROM cart WHERE user_id=?", (uid,))
            self.conn.execute("COMMIT")
            return "ok", oid
        except Exception:
            self.conn.execute("ROLLBACK")
            raise

    def get_order(self, oid: int):
        return self.conn.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()

    def order_items(self, oid: int):
        return self.conn.execute(
            "SELECT * FROM order_items WHERE order_id=? ORDER BY id", (oid,)
        ).fetchall()

    def list_orders(self, status: str | None = None, user_id: int | None = None, limit: int = 10):
        where, args = [], []
        if status:
            where.append("status=?")
            args.append(status)
        if user_id:
            where.append("user_id=?")
            args.append(user_id)
        sql = "SELECT * FROM orders"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY id DESC LIMIT ?"
        return self.conn.execute(sql, (*args, limit)).fetchall()

    def search_orders(self, q: str, limit: int = 10):
        like = f"%{q}%"
        oid = int(q) if q.isdigit() and len(q) <= 9 else -1
        return self.conn.execute(
            "SELECT * FROM orders WHERE id=? OR phone LIKE ? OR user_name LIKE ? "
            "ORDER BY id DESC LIMIT ?",
            (oid, like, like, limit),
        ).fetchall()

    def set_status(self, oid: int, status: str) -> None:
        self.conn.execute("UPDATE orders SET status=? WHERE id=?", (status, oid))

    def stats(self) -> dict:
        today = now_str()[:10]
        month = today[:7]

        def agg(where: str, arg: str | None):
            sql = (
                "SELECT COUNT(*) AS c, "
                "COALESCE(SUM(CASE WHEN status!='cancelled' THEN total END), 0) AS s FROM orders "
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

    # ---------- zaxira ----------
    def backup(self, dst: Path) -> None:
        dst = Path(dst)
        dst.parent.mkdir(parents=True, exist_ok=True)
        target = sqlite3.connect(str(dst))
        try:
            self.conn.backup(target)
        finally:
            target.close()
