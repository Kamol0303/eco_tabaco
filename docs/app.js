// ECO Innovation Tobacco - Telegram Mini App
const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;

if (tg) {
  try {
    tg.ready();
    tg.expand();
  } catch (e) {
    console.error("Telegram WebApp ready error:", e);
  }
}

// 3 asosiy mahsulot (har biri 225 000 so'm)
const PRODUCTS = [
  {
    id: 1,
    key: "mint",
    name: "ECO Mint",
    badge: "MINT FLAVOR",
    price: 225000,
    desc: "Muzdek tetiklashtiruvchi tabiiy yalpiz ifori va yuqori sifatli fermentlangan tamaki.",
    image: "images/mint.jpg"
  },
  {
    id: 2,
    key: "classic",
    name: "ECO Classic",
    badge: "ORIGINAL CLASSIC",
    price: 225000,
    desc: "Klassik an'anaviy retsept bo'yicha tozalangan yumshoq va boy tamaki ta'mi.",
    image: "images/classic.jpg"
  },
  {
    id: 3,
    key: "premium",
    name: "ECO Premium",
    badge: "EXCLUSIVE LUXE",
    price: 225000,
    desc: "Maxsus tanlangan elita tamaki barglarining chuqur va uzoq saqlanuvchi ifori.",
    image: "images/premium.jpg"
  }
];

// Savatcha holati: { 1: 0, 2: 0, 3: 0 }
const cart = { 1: 0, 2: 0, 3: 0 };
let currentCoords = null;

function formatMoney(amount) {
  return amount.toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ") + " so'm";
}

function renderProducts() {
  const container = document.getElementById("productsList");
  if (!container) return;

  container.innerHTML = PRODUCTS.map(p => {
    const qty = cart[p.id] || 0;
    return `
      <div class="product-card ${qty > 0 ? 'has-qty' : ''}" id="card-${p.id}">
        <div class="card-top">
          <img src="${p.image}" alt="${p.name}" class="product-img" onerror="this.src='data:image/svg+xml,%3Csvg xmlns=\\'http://www.w3.org/2000/svg\\' viewBox=\\'0 0 100 100\\' fill=\\'%23111\\'%3E%3Ctext y=\\'55\\' x=\\'50\\' fill=\\'%23e6b82e\\' font-size=\\'14\\' text-anchor=\\'middle\\'%3EECO%3C/text%3E%3C/svg%3E'" />
          <div class="product-info">
            <span class="product-badge">${p.badge}</span>
            <h3 class="product-title">${p.name}</h3>
            <p class="product-desc">${p.desc}</p>
            <div class="product-price">${formatMoney(p.price)}</div>
          </div>
        </div>
        <div class="card-bottom">
          <span class="qty-label">Miqdori:</span>
          <div class="qty-control">
            <button type="button" class="qty-btn" onclick="changeQty(${p.id}, -1)">−</button>
            <input type="number" 
                   min="0" 
                   max="999" 
                   value="${qty}" 
                   class="qty-input" 
                   id="qty-input-${p.id}" 
                   oninput="onQtyInput(${p.id}, this.value)" 
                   onchange="onQtyInput(${p.id}, this.value)" />
            <button type="button" class="qty-btn" onclick="changeQty(${p.id}, 1)">+</button>
          </div>
        </div>
      </div>
    `;
  }).join("");

  updateTotals();
}

function changeQty(productId, delta) {
  const current = cart[productId] || 0;
  const next = Math.max(0, Math.min(999, current + delta));
  setQty(productId, next);
}

function onQtyInput(productId, rawValue) {
  let val = parseInt(rawValue, 10);
  if (isNaN(val) || val < 0) val = 0;
  if (val > 999) val = 999;
  setQty(productId, val);
}

function setQty(productId, val) {
  cart[productId] = val;
  const input = document.getElementById(`qty-input-${productId}`);
  if (input && parseInt(input.value, 10) !== val) {
    input.value = val;
  }
  const card = document.getElementById(`card-${productId}`);
  if (card) {
    if (val > 0) card.classList.add("has-qty");
    else card.classList.remove("has-qty");
  }
  updateTotals();
}

function updateTotals() {
  let totalQty = 0;
  let totalPrice = 0;

  PRODUCTS.forEach(p => {
    const qty = cart[p.id] || 0;
    totalQty += qty;
    totalPrice += qty * p.price;
  });

  const barCount = document.getElementById("barCount");
  const barTotal = document.getElementById("barTotal");
  const btnOrder = document.getElementById("btnOrder");

  if (barCount) barCount.innerText = totalQty > 0 ? `${totalQty} dona mahsulot` : "Tanlanmadi";
  if (barTotal) barTotal.innerText = formatMoney(totalPrice);
  if (btnOrder) btnOrder.disabled = totalQty === 0;
}

// Modalni ochish
function openOrderModal() {
  const modal = document.getElementById("orderModal");
  const summaryBox = document.getElementById("orderSummaryBox");
  const inputName = document.getElementById("customerName");
  const inputPhone = document.getElementById("customerPhone");

  let summaryHtml = "";
  let totalPrice = 0;

  PRODUCTS.forEach(p => {
    const qty = cart[p.id] || 0;
    if (qty > 0) {
      const sum = qty * p.price;
      totalPrice += sum;
      summaryHtml += `
        <div class="summary-item">
          <span>${p.name} × ${qty} ta</span>
          <span>${formatMoney(sum)}</span>
        </div>
      `;
    }
  });

  summaryHtml += `
    <div class="summary-item summary-total">
      <span>Jami:</span>
      <span>${formatMoney(totalPrice)}</span>
    </div>
  `;

  summaryBox.innerHTML = summaryHtml;

  // Telegram foydalanuvchi ma'lumotlarini olish
  if (tg && tg.initDataUnsafe && tg.initDataUnsafe.user) {
    const u = tg.initDataUnsafe.user;
    if (inputName && !inputName.value) {
      inputName.value = [u.first_name, u.last_name].filter(Boolean).join(" ");
    }
  }

  modal.classList.add("active");
}

function closeOrderModal() {
  const modal = document.getElementById("orderModal");
  if (modal) modal.classList.remove("active");
}

// Geolokatsiyani olish
function getGpsLocation() {
  const btn = document.getElementById("btnGps");
  const addressInput = document.getElementById("customerAddress");
  if (!navigator.geolocation) {
    alert("Brauzeringizda GPS aniqlash qo'llab-quvvatlanmaydi. Manzilni qo'lda kiriting.");
    return;
  }

  btn.innerText = "⏳ Geolokatsiya olinmoqda...";
  btn.disabled = true;

  navigator.geolocation.getCurrentPosition(
    (pos) => {
      const lat = pos.coords.latitude;
      const lon = pos.coords.longitude;
      currentCoords = { lat, lon };
      addressInput.value = `📍 GPS: ${lat.toFixed(6)}, ${lon.toFixed(6)}`;
      btn.innerText = "✅ Joylashuv aniqlandi!";
      btn.disabled = false;
    },
    (err) => {
      console.warn("GPS error:", err);
      alert("Joylashuvni aniqlab bo'lmadi. Iltimos, manzilni qo'lda yozing.");
      btn.innerText = "📍 Mening geolokatsiyam";
      btn.disabled = false;
    },
    { enableHighAccuracy: true, timeout: 8000 }
  );
}

// Buyurtmani jo'natish
async function submitOrder() {
  const name = (document.getElementById("customerName").value || "").trim();
  const phone = (document.getElementById("customerPhone").value || "").trim();
  const address = (document.getElementById("customerAddress").value || "").trim();
  const note = (document.getElementById("customerNote").value || "").trim();

  if (!phone) {
    alert("Iltimos, telefon raqamingizni kiriting!");
    document.getElementById("customerPhone").focus();
    return;
  }

  const items = [];
  let totalPrice = 0;
  PRODUCTS.forEach(p => {
    const qty = cart[p.id] || 0;
    if (qty > 0) {
      items.push({ id: p.id, key: p.key, name: p.name, qty: qty, price: p.price });
      totalPrice += qty * p.price;
    }
  });

  if (items.length === 0) {
    alert("Savatcha bo'sh!");
    return;
  }

  const payload = {
    user: tg && tg.initDataUnsafe && tg.initDataUnsafe.user ? tg.initDataUnsafe.user : null,
    customer_name: name || "Mijoz",
    customer_phone: phone,
    delivery_address: address,
    coords: currentCoords,
    notes: note,
    items: items,
    total: totalPrice,
    timestamp: new Date().toISOString()
  };

  const btnSubmit = document.getElementById("btnSubmit");
  btnSubmit.innerText = "Yuborilmoqda...";
  btnSubmit.disabled = true;

  // 1-usul: Telegram WebApp sendData (eng tez va ishonchli usul)
  let sentViaTg = false;
  try {
    if (tg && typeof tg.sendData === "function") {
      tg.sendData(JSON.stringify(payload));
      sentViaTg = true;
    }
  } catch (e) {
    console.warn("sendData not supported or failed:", e);
  }

  // 2-usul: Backend API orqali yuborish (agar veb server ishlab turgan bo'lsa)
  try {
    const apiUrl = window.location.origin.includes("github.io")
      ? "https://eco-tabaco.onrender.com/api/order"
      : "/api/order";

    await fetch(apiUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
  } catch (apiErr) {
    console.log("API background post fallback:", apiErr);
  }

  // Muvaffaqiyatli oynani ko'rsatish
  document.getElementById("modalBody").innerHTML = `
    <div class="success-card">
      <div class="success-icon">🎉</div>
      <h3>Buyurtmangiz qabul qilindi!</h3>
      <p>Tez orada operatorimiz siz bilan bog'lanadi va yetkazib berish boshlanadi.</p>
      <button type="button" class="btn-submit-order" onclick="onOrderDone()">Telegramga qaytish</button>
    </div>
  `;
}

function onOrderDone() {
  if (tg) {
    try { tg.close(); } catch (e) {}
  } else {
    location.reload();
  }
}

// Boshlang'ich yuklash
document.addEventListener("DOMContentLoaded", () => {
  renderProducts();

  if (tg && tg.initDataUnsafe && tg.initDataUnsafe.user) {
    const u = tg.initDataUnsafe.user;
    const badge = document.getElementById("userBadge");
    if (badge) {
      badge.innerText = u.first_name || u.username || "Mijoz";
    }
  }
});
