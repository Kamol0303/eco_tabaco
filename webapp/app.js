/* ECO · Telegram Mini App Frontend (Mijoz va Admin alohida) */
(function () {
  "use strict";

  const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
  const DEFAULT_COORDS = { lat: 41.2995, lon: 69.2401 }; // Toshkent markazi

  const state = {
    user: null,
    products: [],
    cart: { items: [], total: 0, total_qty: 0, max_qty: 50 },
    orders: [],
    statuses: {},
    flow: [],
    activeTab: "catalog",
    activeAdminTab: "orders",
    modalProductId: null,
    adminFilter: "all",
    adminSearch: "",
    adminData: null,
    map: null,
    marker: null,
    lat: DEFAULT_COORDS.lat,
    lon: DEFAULT_COORDS.lon,
    orderPlacedSuccess: false,
  };

  // ---------------- Yordamchilar ----------------
  function esc(val) {
    return String(val ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function money(n) {
    return Number(n || 0)
      .toLocaleString("en-US")
      .replace(/,/g, " ");
  }

  function fmtDt(s) {
    if (!s) return "-";
    const m = /^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2})/.exec(s);
    if (!m) return s;
    return `${m[3]}.${m[2]}.${m[1]} ${m[4]}:${m[5]}`;
  }

  function haptic(type = "light") {
    try {
      if (tg && tg.HapticFeedback) {
        if (type === "select") tg.HapticFeedback.selectionChanged();
        else tg.HapticFeedback.impactOccurred(type);
      }
    } catch (_) {}
  }

  let toastTimer = null;
  function showToast(msg, isError = false) {
    const el = document.getElementById("toast");
    el.textContent = msg;
    el.classList.toggle("error", Boolean(isError));
    el.classList.remove("hidden");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.add("hidden"), 2800);
  }

  async function api(path, options = {}) {
    const headers = Object.assign(
      { "Content-Type": "application/json" },
      options.headers || {}
    );
    if (tg && tg.initData) {
      headers["X-Telegram-Init-Data"] = tg.initData;
    }
    const res = await fetch(path, Object.assign({}, options, { headers }));
    let data = {};
    try {
      data = await res.json();
    } catch (_) {}
    if (!res.ok || data.ok === false) {
      const err = new Error(data.error || "Server bilan bog'lanishda xatolik");
      err.status = res.status;
      err.code = data.code;
      throw err;
    }
    return data;
  }

  function getCartQty(pid) {
    const item = state.cart.items.find((i) => i.product_id === pid);
    return item ? item.qty : 0;
  }

  function supportsTgContact() {
    return Boolean(tg && tg.initData && typeof tg.requestContact === "function");
  }

  // ---------------- Ko'rinishlar boshqaruvi ----------------
  function hideAllViews() {
    document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
  }

  function showCustomerTab(tab) {
    if (state.user && state.user.is_admin) return;
    state.activeTab = tab;
    if (tab !== "cart") {
      state.orderPlacedSuccess = false;
    }

    document.querySelectorAll("#customerNav .nav-item").forEach((b) => {
      b.classList.toggle("active", b.dataset.tab === tab);
    });

    hideAllViews();
    const mapTabToView = {
      catalog: "viewCatalog",
      cart: "viewCart",
      orders: "viewOrders",
      profile: "viewProfile",
    };
    const target = document.getElementById(mapTabToView[tab] || "viewCatalog");
    if (target) target.classList.add("active");
    updateFloatingCartBar();

    if (tab === "cart") {
      renderCart();
      setTimeout(ensureMapInitialized, 60);
    } else if (tab === "orders") {
      refreshOrders();
    } else if (tab === "profile") {
      renderProfile();
    }
    haptic("select");
  }

  function showAdminTab(tab) {
    if (!state.user || !state.user.is_admin) return;
    state.activeAdminTab = tab;

    document.querySelectorAll("#adminNav .nav-item").forEach((b) => {
      b.classList.toggle("active", b.dataset.adminTab === tab);
    });

    hideAllViews();
    const mapTabToView = {
      orders: "viewAdminOrders",
      products: "viewAdminProducts",
      stats: "viewAdminStats",
      users: "viewAdminUsers",
    };
    const target = document.getElementById(mapTabToView[tab] || "viewAdminOrders");
    if (target) target.classList.add("active");

    loadAdminOverview();
    haptic("select");
  }

  function updateFloatingCartBar() {
    const bar = document.getElementById("floatingCartBar");
    if (state.user && state.user.is_admin) {
      bar.classList.add("hidden");
      return;
    }
    const show =
      state.activeTab === "catalog" &&
      state.cart.total_qty > 0 &&
      state.user &&
      state.user.age_ok;
    bar.classList.toggle("hidden", !show);
    if (show) {
      document.getElementById("floatingCartCount").textContent = `${state.cart.total_qty} ta mahsulot`;
      document.getElementById("floatingCartTotal").textContent = `${money(state.cart.total)} so'm`;
    }
  }

  function updateCartBadges() {
    const badge = document.getElementById("navCartBadge");
    if (!state.user || state.user.is_admin) {
      badge.classList.add("hidden");
      return;
    }
    if (state.cart.total_qty > 0) {
      badge.textContent = String(state.cart.total_qty);
      badge.classList.remove("hidden");
    } else {
      badge.classList.add("hidden");
    }
    updateFloatingCartBar();
  }

  function renderHeader() {
    const u = state.user;
    if (!u) return;

    const sub = document.getElementById("brandSubTitle");
    const nameEl = document.getElementById("userBadgeName");

    if (u.is_admin) {
      sub.textContent = "ADMIN BOSHQARUV PANELI";
      nameEl.textContent = `🛡 Admin: ${u.name}`;
      document.getElementById("customerNav").classList.add("hidden");
      document.getElementById("adminNav").classList.remove("hidden");
      document.getElementById("floatingCartBar").classList.add("hidden");
      document.getElementById("ageGateModal").classList.add("hidden");
    } else {
      sub.textContent = "INNOVATION TOBACCO";
      nameEl.textContent = u.name || "Mijoz";
      document.getElementById("adminNav").classList.add("hidden");
      document.getElementById("customerNav").classList.remove("hidden");
    }
  }

  // ---------------- Mijoz: Katalog ----------------
  function renderCatalog() {
    if (state.user && state.user.is_admin) return;

    const grid = document.getElementById("catalogGrid");
    document.getElementById("productCountLabel").textContent = `${state.products.length} turdagi mahsulot`;

    if (!state.products.length) {
      grid.innerHTML = `<div class="empty-card"><h3>Mahsulotlar hozircha mavjud emas</h3></div>`;
      return;
    }

    grid.innerHTML = state.products
      .map((p) => {
        const qty = getCartQty(p.id);
        const keyClass = esc(p.key);
        const imgHtml = p.image_url
          ? `<img src="${esc(p.image_url)}" alt="${esc(p.name)}" loading="lazy" />`
          : "";
        const controlHtml = `
          <div class="qty-pill ${qty === 0 ? "is-zero" : ""}" data-pid="${p.id}">
            <button type="button" data-action="dec" data-pid="${p.id}" ${qty === 0 ? "disabled" : ""} aria-label="Kamaytirish">−</button>
            <span>${qty}</span>
            <button type="button" data-action="inc" data-pid="${p.id}" aria-label="Ko'paytirish">+</button>
          </div>`;

        return `
          <article class="product-card ${qty > 0 ? "in-cart" : ""}" data-pid="${p.id}">
            <div class="product-media" data-action="detail" data-pid="${p.id}">
              ${imgHtml}
              <span class="variant-tag ${keyClass}">${esc(p.key)}</span>
            </div>
            <div class="product-body">
              <h3 class="product-title" data-action="detail" data-pid="${p.id}">${esc(p.name)}</h3>
              <p class="product-desc">${esc(p.description)}</p>
              <div class="product-footer">
                <span class="product-price">${money(p.price)} so'm</span>
                ${controlHtml}
              </div>
            </div>
          </article>
        `;
      })
      .join("");
  }

  async function updateCartQty(pid, newQty) {
    const clamped = Math.max(0, Math.min(newQty, state.cart.max_qty || 50));
    try {
      const data = await api("/api/cart", {
        method: "POST",
        body: JSON.stringify({ product_id: pid, qty: clamped }),
      });
      state.cart = data.cart;
      haptic("light");
      renderCatalog();
      updateCartBadges();
      if (state.activeTab === "cart") renderCart();
      if (state.modalProductId === pid) syncProductModal();
    } catch (e) {
      showToast(e.message, true);
    }
  }

  function openProductModal(pid) {
    const p = state.products.find((item) => item.id === pid);
    if (!p) return;
    state.modalProductId = pid;
    const modal = document.getElementById("productModal");
    document.getElementById("modalProductImg").src = p.image_url || "";
    document.getElementById("modalProductImg").alt = p.name;
    const tag = document.getElementById("modalProductTag");
    tag.textContent = p.key.toUpperCase();
    tag.className = `variant-tag ${p.key}`;
    document.getElementById("modalProductName").textContent = p.name;
    document.getElementById("modalProductPrice").textContent = `${money(p.price)} so'm`;
    document.getElementById("modalProductDesc").textContent = p.description;
    syncProductModal();
    modal.classList.remove("hidden");
    modal.setAttribute("aria-hidden", "false");
    haptic("select");
  }

  function syncProductModal() {
    if (!state.modalProductId) return;
    const qty = getCartQty(state.modalProductId);
    document.getElementById("modalQtyVal").textContent = String(qty);
    document.getElementById("modalDecBtn").disabled = qty === 0;
    const primary = document.getElementById("modalPrimaryBtn");
    primary.textContent = qty > 0 ? "Savatchaga o'tish" : "Savatchaga qo'shish";
  }

  function closeProductModal() {
    state.modalProductId = null;
    const modal = document.getElementById("productModal");
    modal.classList.add("hidden");
    modal.setAttribute("aria-hidden", "true");
  }

  // ---------------- Mijoz: Savatcha & Joylashuv ----------------
  function renderCart() {
    const successCard = document.getElementById("orderSuccessCard");
    const emptyCard = document.getElementById("cartEmpty");
    const filled = document.getElementById("cartFilled");
    const clearBtn = document.getElementById("btnClearCart");

    if (state.orderPlacedSuccess) {
      successCard.classList.remove("hidden");
      emptyCard.classList.add("hidden");
      filled.classList.add("hidden");
      clearBtn.classList.add("hidden");
      return;
    }
    successCard.classList.add("hidden");

    if (!state.cart.items.length) {
      emptyCard.classList.remove("hidden");
      filled.classList.add("hidden");
      clearBtn.classList.add("hidden");
      return;
    }

    emptyCard.classList.add("hidden");
    filled.classList.remove("hidden");
    clearBtn.classList.remove("hidden");

    document.getElementById("cartItemsList").innerHTML = state.cart.items
      .map((it) => {
        const thumb = it.image_url
          ? `<img class="cart-thumb" src="${esc(it.image_url)}" alt="${esc(it.name)}" />`
          : `<div class="cart-thumb"></div>`;
        return `
          <div class="cart-item">
            ${thumb}
            <div class="cart-item-info">
              <div class="cart-item-title">${esc(it.name)}</div>
              <div class="cart-item-sub">${it.qty} × ${money(it.price)} so'm</div>
              <div class="cart-item-price">${money(it.subtotal)} so'm</div>
            </div>
            <div class="cart-item-actions">
              <div class="qty-pill">
                <button type="button" data-cart-act="dec" data-pid="${it.product_id}">−</button>
                <span>${it.qty}</span>
                <button type="button" data-cart-act="inc" data-pid="${it.product_id}">+</button>
              </div>
              <button type="button" class="remove-link" data-cart-act="del" data-pid="${it.product_id}">O'chirish</button>
            </div>
          </div>
        `;
      })
      .join("");

    document.getElementById("cartTotalQty").textContent = `${state.cart.total_qty} ta`;
    document.getElementById("cartTotalSum").textContent = `${money(state.cart.total)} so'm`;

    const u = state.user;
    const regCard = document.getElementById("checkoutRegCard");
    const preview = document.getElementById("checkoutUserPreview");
    const placeBtn = document.getElementById("btnPlaceOrder");

    if (!u || !u.is_registered) {
      regCard.classList.remove("hidden");
      document.getElementById("regNameInput").value = (u && u.name) || "";
      document.getElementById("regPhoneInput").value = (u && u.phone) || "+998";
      document.getElementById("btnTgContact").classList.toggle("hidden", !supportsTgContact());
      preview.textContent = "Avval aloqa ma'lumotlaringizni saqlang.";
      placeBtn.disabled = true;
    } else {
      regCard.classList.add("hidden");
      preview.textContent = `👤 ${u.name} · 📞 ${u.phone}`;
      placeBtn.disabled = false;
    }
  }

  function ensureMapInitialized() {
    const host = document.getElementById("deliveryMap");
    const fallback = document.getElementById("mapOfflineFallback");
    if (!host || !window.L) {
      if (fallback) fallback.classList.remove("hidden");
      return;
    }

    if (!state.map) {
      state.map = L.map(host, {
        center: [state.lat, state.lon],
        zoom: 13,
        zoomControl: true,
        attributionControl: false,
      });

      const tiles = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
      });
      tiles.addTo(state.map);

      const pinIcon = L.divIcon({
        className: "eco-pin-wrap",
        html: `<div style="width:22px;height:22px;border-radius:50%;background:#e6b82e;border:3px solid #0b0e0c;box-shadow:0 0 0 4px rgba(230,184,46,0.35);"></div>`,
        iconSize: [22, 22],
        iconAnchor: [11, 11],
      });

      state.marker = L.marker([state.lat, state.lon], { draggable: true, icon: pinIcon }).addTo(state.map);
      state.marker.on("dragend", () => {
        const pos = state.marker.getLatLng();
        setCoordinates(pos.lat, pos.lng, false);
      });
      state.map.on("click", (e) => {
        setCoordinates(e.latlng.lat, e.latlng.lng, false);
      });
    } else {
      state.map.invalidateSize();
    }
  }

  function setCoordinates(lat, lon, panMap = true) {
    state.lat = Number(lat);
    state.lon = Number(lon);
    document.getElementById("latInput").value = state.lat.toFixed(6);
    document.getElementById("lonInput").value = state.lon.toFixed(6);
    if (state.marker) {
      state.marker.setLatLng([state.lat, state.lon]);
    }
    if (panMap && state.map) {
      state.map.setView([state.lat, state.lon], Math.max(state.map.getZoom(), 15));
    }
  }

  function detectGeolocation() {
    if (!navigator.geolocation) {
      showToast("Qurilma geolokatsiyani qo'llab-quvvatlamaydi.", true);
      return;
    }
    const btn = document.getElementById("btnDetectLocation");
    btn.disabled = true;
    btn.textContent = "⏳ Joylashuv aniqlanmoqda...";

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setCoordinates(pos.coords.latitude, pos.coords.longitude, true);
        showToast("Joylashuv aniqlandi ✅");
        btn.disabled = false;
        btn.innerHTML = `<span class="btn-icon">🎯</span> Mening hozirgi joylashuvim`;
      },
      () => {
        showToast("GPS ruxsati berilmadi. Xaritadan nuqtani tanlang.", true);
        btn.disabled = false;
        btn.innerHTML = `<span class="btn-icon">🎯</span> Mening hozirgi joylashuvim`;
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  }

  async function saveRegistration(name, phone) {
    const data = await api("/api/register", {
      method: "POST",
      body: JSON.stringify({ name, phone }),
    });
    state.user = data.user;
    renderHeader();
    renderCart();
    renderProfile();
    showToast("Ma'lumotlar saqlandi ✅");
  }

  function requestTelegramContact(targetInputId, targetNameId) {
    if (!supportsTgContact()) return;
    tg.requestContact((sent, event) => {
      if (sent && event && event.responseUnsafe && event.responseUnsafe.contact) {
        const c = event.responseUnsafe.contact;
        const phone = c.phone_number.startsWith("+") ? c.phone_number : `+${c.phone_number}`;
        document.getElementById(targetInputId).value = phone;
        const fullName = `${c.first_name || ""} ${c.last_name || ""}`.trim();
        if (fullName && targetNameId) {
          document.getElementById(targetNameId).value = fullName;
        }
        saveRegistration(
          (document.getElementById(targetNameId)?.value || state.user.name).trim(),
          phone
        ).catch((e) => showToast(e.message, true));
      }
    });
  }

  async function placeOrder() {
    const btn = document.getElementById("btnPlaceOrder");
    const lat = parseFloat(document.getElementById("latInput").value);
    const lon = parseFloat(document.getElementById("lonInput").value);
    if (Number.isNaN(lat) || Number.isNaN(lon)) {
      showToast("Joylashuv koordinatalarini kiriting.", true);
      return;
    }

    btn.disabled = true;
    btn.textContent = "⏳ Yuborilmoqda...";
    try {
      const data = await api("/api/orders", {
        method: "POST",
        body: JSON.stringify({
          lat,
          lon,
          expected_total: state.cart.total,
        }),
      });
      state.cart = data.cart;
      state.orders = [data.order, ...state.orders];
      state.orderPlacedSuccess = true;
      document.getElementById("successOrderId").textContent = `№${data.order.id}`;
      updateCartBadges();
      renderCatalog();
      renderCart();
      haptic("heavy");
      showToast(`Buyurtma №${data.order.id} qabul qilindi!`);
    } catch (e) {
      if (e.code === "price_changed") {
        await bootstrap();
      }
      showToast(e.message, true);
    } finally {
      btn.disabled = false;
      btn.textContent = "✅ Buyurtmani tasdiqlash";
    }
  }

  // ---------------- Mijoz: Buyurtmalarim ----------------
  async function refreshOrders() {
    try {
      const data = await api("/api/orders");
      state.orders = data.orders;
      renderOrders();
    } catch (e) {
      showToast(e.message, true);
    }
  }

  function renderOrderProgress(status) {
    if (status === "cancelled") return "";
    const steps = ["new", "accepted", "preparing", "delivering", "done"];
    const idx = steps.indexOf(status);
    return `
      <div class="order-progress" aria-label="Buyurtma bosqichlari">
        ${steps
          .map((_, i) => {
            let cls = "prog-step";
            if (status === "done" || i < idx) cls += " done";
            else if (i === idx) cls += " active";
            return `<div class="${cls}"></div>`;
          })
          .join("")}
      </div>
    `;
  }

  function renderOrders() {
    const list = document.getElementById("ordersList");
    if (!state.orders.length) {
      list.innerHTML = `
        <div class="empty-card">
          <div class="empty-icon">📦</div>
          <h3>Siz hali buyurtma bermagansiz</h3>
          <p>Birinchi buyurtmangizni katalogdan berishingiz mumkin.</p>
          <button type="button" class="btn-primary" data-go-tab="catalog">Katalogga o'tish</button>
        </div>
      `;
      return;
    }

    list.innerHTML = state.orders
      .map((o) => {
        const itemsHtml = o.items
          .map(
            (it) => `
              <div class="order-item-line">
                <span>${esc(it.product_name)} × ${it.qty}</span>
                <strong>${money(it.subtotal)} so'm</strong>
              </div>
            `
          )
          .join("");
        return `
          <article class="order-card">
            <div class="order-card-head">
              <div>
                <div class="order-id">Buyurtma №${o.id}</div>
                <div class="order-date">${fmtDt(o.created_at)}</div>
              </div>
              <span class="status-pill ${esc(o.status)}">${esc(o.status_emoji)} ${esc(o.status_label)}</span>
            </div>
            ${renderOrderProgress(o.status)}
            <div class="order-items-mini">${itemsHtml}</div>
            <div class="order-card-foot">
              <a class="map-link" href="https://www.google.com/maps?q=${o.lat},${o.lon}" target="_blank" rel="noopener">
                🗺 Xaritada ko'rish
              </a>
              <strong class="gold-text">${money(o.total)} so'm</strong>
            </div>
          </article>
        `;
      })
      .join("");
  }

  // ---------------- Mijoz: Profil ----------------
  function renderProfile() {
    const u = state.user;
    if (!u) return;
    const initial = (u.name || "E").trim().charAt(0).toUpperCase() || "E";
    document.getElementById("profileAvatar").textContent = initial;
    document.getElementById("profileDisplayName").textContent = u.name || "Foydalanuvchi";
    document.getElementById("profileDisplayPhone").textContent = u.phone || "Telefon raqam kiritilmagan";
    document.getElementById("profileAgeBadge").textContent = u.age_ok ? "✅ 21+ tasdiqlangan" : "🔞 21+";
    document.getElementById("profileIdBadge").textContent = `ID: ${u.tg_id}`;

    document.getElementById("profNameInput").value = u.name || "";
    document.getElementById("profPhoneInput").value = u.phone || "+998";
    document.getElementById("btnProfTgContact").classList.toggle("hidden", !supportsTgContact());
    document.getElementById("profRegDate").textContent = u.registered_at
      ? `Ro'yxatdan o'tgan sana: ${fmtDt(u.registered_at)}`
      : "Buyurtma berish uchun telefon raqamingizni saqlang.";
  }

  // ---------------- FAQAT ADMIN: Boshqaruv Paneli ----------------
  async function loadAdminOverview() {
    if (!state.user || !state.user.is_admin) return;
    try {
      const qs = new URLSearchParams({
        status: state.adminFilter,
        q: state.adminSearch,
      });
      const data = await api(`/api/admin/overview?${qs.toString()}`);
      state.adminData = data;
      renderAdmin();
    } catch (e) {
      showToast(e.message, true);
    }
  }

  function renderAdmin() {
    const d = state.adminData;
    if (!d) return;

    const s = d.stats;
    // 1. Statistika qismi
    document.getElementById("adminStatsGrid").innerHTML = `
      <div class="stat-card">
        <div class="stat-label">📅 Bugun</div>
        <div class="stat-val">${money(s.today[1])} so'm</div>
        <div class="stat-sub">${s.today[0]} ta buyurtma</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">🗓 Shu oy</div>
        <div class="stat-val">${money(s.month[1])} so'm</div>
        <div class="stat-sub">${s.month[0]} ta buyurtma</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">🧮 Jami tushum</div>
        <div class="stat-val">${money(s.total[1])} so'm</div>
        <div class="stat-sub">${s.total[0]} ta buyurtma</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">👥 Ro'yxatdan o'tganlar</div>
        <div class="stat-val">${s.users} ta</div>
        <div class="stat-sub">Yangi: ${s.by_status.new || 0} ta</div>
      </div>
    `;

    // 2. Buyurtmalar filtri
    const chips = [
      `<button type="button" class="chip-btn ${state.adminFilter === "all" ? "active" : ""}" data-status="all">Hammasi</button>`,
      ...Object.keys(state.statuses).map((code) => {
        const st = state.statuses[code];
        const cnt = s.by_status[code] || 0;
        return `<button type="button" class="chip-btn ${state.adminFilter === code ? "active" : ""}" data-status="${code}">${esc(st.emoji)} ${esc(st.label)} (${cnt})</button>`;
      }),
    ];
    document.getElementById("adminStatusChips").innerHTML = chips.join("");

    // 3. Buyurtmalar ro'yxati
    const ordersList = document.getElementById("adminOrdersList");
    if (!d.orders.length) {
      ordersList.innerHTML = `<div class="empty-card"><p>Buyurtmalar topilmadi.</p></div>`;
    } else {
      ordersList.innerHTML = d.orders
        .map((o) => {
          const itemsHtml = o.items
            .map(
              (it) => `
                <div class="order-item-line">
                  <span>${esc(it.product_name)} × ${it.qty}</span>
                  <span>${money(it.subtotal)} so'm</span>
                </div>
              `
            )
            .join("");

          const actionsHtml = !o.is_final
            ? `<div class="admin-status-actions">
                ${state.flow
                  .filter((code) => code !== o.status)
                  .map((code) => {
                    const st = state.statuses[code];
                    const danger = code === "cancelled" ? "danger" : "";
                    return `<button type="button" class="status-action-btn ${danger}" data-oid="${o.id}" data-new-status="${code}">${esc(st.emoji)} ${esc(st.label)}</button>`;
                  })
                  .join("")}
              </div>`
            : "";

          return `
            <article class="order-card">
              <div class="order-card-head">
                <div>
                  <div class="order-id">№${o.id} · ${esc(o.user_name)}</div>
                  <div class="order-date">
                    <a class="map-link" href="tel:${esc(o.phone)}">${esc(o.phone)}</a> · ${fmtDt(o.created_at)}
                  </div>
                </div>
                <span class="status-pill ${esc(o.status)}">${esc(o.status_emoji)} ${esc(o.status_label)}</span>
              </div>
              <div class="order-items-mini">${itemsHtml}</div>
              <div class="order-card-foot">
                <a class="map-link" href="https://www.google.com/maps?q=${o.lat},${o.lon}" target="_blank" rel="noopener">
                  🗺 ${o.lat.toFixed(4)}, ${o.lon.toFixed(4)}
                </a>
                <strong class="gold-text">${money(o.total)} so'm</strong>
              </div>
              ${actionsHtml}
            </article>
          `;
        })
        .join("");
    }

    // 4. Mahsulotlar va narxlar
    document.getElementById("adminProductsList").innerHTML = d.products
      .map(
        (p) => `
          <div class="admin-product-card">
            <div class="admin-product-top">
              <div>
                <strong>${esc(p.name)}</strong>
                <div class="muted-label small">Kalit: ${esc(p.key)} · ${p.active ? "🟢 Faol" : "🔴 O'chirilgan"}</div>
              </div>
              <button type="button" class="btn-secondary" data-toggle-pid="${p.id}">
                ${p.active ? "O'chirish" : "Yoqish"}
              </button>
            </div>
            <div class="admin-price-row">
              <input type="number" min="1000" max="100000000" step="1000" value="${p.price}" id="priceInput-${p.id}" />
              <button type="button" class="btn-primary btn-sm" data-save-price-pid="${p.id}">Narxni saqlash</button>
            </div>
          </div>
        `
      )
      .join("");

    // 5. Mijozlar ro'yxati
    document.getElementById("adminUsersList").innerHTML = d.users.length
      ? d.users
          .map(
            (u) => `
              <div class="user-row-card">
                <div>
                  <strong>${esc(u.name)}</strong>
                  <div class="muted-label small">ID: ${u.tg_id} · ${fmtDt(u.registered_at)}</div>
                </div>
                <a class="map-link" href="tel:${esc(u.phone)}">${esc(u.phone)}</a>
              </div>
            `
          )
          .join("")
      : `<div class="empty-card"><p>Ro'yxatdan o'tgan mijozlar yo'q.</p></div>`;
  }

  // ---------------- Yosh chegarasi (21+) ----------------
  function syncAgeGate() {
    const gate = document.getElementById("ageGateModal");
    if (!state.user || state.user.is_admin || state.user.age_ok) {
      gate.classList.add("hidden");
      return;
    }
    document.getElementById("ageGateActions").classList.remove("hidden");
    document.getElementById("ageBlockedNotice").classList.add("hidden");
    gate.classList.remove("hidden");
  }

  // ---------------- Bootstrap ----------------
  async function bootstrap() {
    try {
      const data = await api("/api/bootstrap");
      state.user = data.user;
      state.products = data.products;
      state.cart = data.cart;
      state.orders = data.orders;
      state.statuses = data.statuses;
      state.flow = data.flow;

      renderHeader();

      if (state.user.is_admin) {
        // ADMIN: Faqat admin panelini ochamiz
        showAdminTab(state.activeAdminTab || "orders");
      } else {
        // MIJOZ: Faqat mijoz do'konini ochamiz
        renderCatalog();
        updateCartBadges();
        renderOrders();
        renderProfile();
        syncAgeGate();
        showCustomerTab(state.activeTab || "catalog");
      }
    } catch (e) {
      if (e.status === 401) {
        document.getElementById("blockedMessage").textContent = e.message;
        hideAllViews();
        document.getElementById("viewBlocked").classList.add("active");
      } else {
        showToast(e.message, true);
      }
    }
  }

  // ---------------- Hodisalar ----------------
  function bindEvents() {
    // Mijoz pastki menyusi
    document.getElementById("customerNav").addEventListener("click", (e) => {
      const btn = e.target.closest(".nav-item");
      if (btn && btn.dataset.tab) showCustomerTab(btn.dataset.tab);
    });

    // Admin pastki menyusi
    document.getElementById("adminNav").addEventListener("click", (e) => {
      const btn = e.target.closest(".nav-item");
      if (btn && btn.dataset.adminTab) showAdminTab(btn.dataset.adminTab);
    });

    // Tezkor yo'naltirish tugmalari
    document.addEventListener("click", (e) => {
      const goBtn = e.target.closest("[data-go-tab]");
      if (goBtn) {
        state.orderPlacedSuccess = false;
        showCustomerTab(goBtn.dataset.goTab);
      }
    });

    document.getElementById("btnGoCartFromFloat").addEventListener("click", () => showCustomerTab("cart"));

    // Katalog amallari (Mijoz)
    document.getElementById("catalogGrid").addEventListener("click", (e) => {
      const target = e.target.closest("[data-action]");
      if (!target) return;
      const pid = Number(target.dataset.pid);
      const act = target.dataset.action;
      if (act === "detail") {
        openProductModal(pid);
      } else if (act === "inc") {
        updateCartQty(pid, getCartQty(pid) + 1);
      } else if (act === "dec") {
        updateCartQty(pid, getCartQty(pid) - 1);
      }
    });

    // Mahsulot batafsil modali
    document.getElementById("btnCloseProductModal").addEventListener("click", closeProductModal);
    document.getElementById("productModal").addEventListener("click", (e) => {
      if (e.target.id === "productModal") closeProductModal();
    });
    document.getElementById("modalIncBtn").addEventListener("click", () => {
      if (state.modalProductId) updateCartQty(state.modalProductId, getCartQty(state.modalProductId) + 1);
    });
    document.getElementById("modalDecBtn").addEventListener("click", () => {
      if (state.modalProductId) updateCartQty(state.modalProductId, getCartQty(state.modalProductId) - 1);
    });
    document.getElementById("modalPrimaryBtn").addEventListener("click", async () => {
      const pid = state.modalProductId;
      if (!pid) return;
      if (getCartQty(pid) === 0) {
        await updateCartQty(pid, 1);
      } else {
        closeProductModal();
        showCustomerTab("cart");
      }
    });

    // Yosh tasdiqlash
    document.getElementById("btnAgeYes").addEventListener("click", async () => {
      try {
        const data = await api("/api/age-confirm", { method: "POST", body: "{}" });
        state.user = data.user;
        syncAgeGate();
        updateFloatingCartBar();
        haptic("medium");
      } catch (e) {
        showToast(e.message, true);
      }
    });
    document.getElementById("btnAgeNo").addEventListener("click", () => {
      document.getElementById("ageGateActions").classList.add("hidden");
      document.getElementById("ageBlockedNotice").classList.remove("hidden");
    });

    // Savatcha amallari
    document.getElementById("cartItemsList").addEventListener("click", (e) => {
      const btn = e.target.closest("[data-cart-act]");
      if (!btn) return;
      const pid = Number(btn.dataset.pid);
      const act = btn.dataset.cartAct;
      const cur = getCartQty(pid);
      if (act === "inc") updateCartQty(pid, cur + 1);
      else if (act === "dec") updateCartQty(pid, cur - 1);
      else if (act === "del") updateCartQty(pid, 0);
    });

    document.getElementById("btnClearCart").addEventListener("click", async () => {
      try {
        const data = await api("/api/cart", { method: "DELETE" });
        state.cart = data.cart;
        renderCatalog();
        renderCart();
        updateCartBadges();
        showToast("Savatcha tozalandi");
      } catch (e) {
        showToast(e.message, true);
      }
    });

    // Buyurtma berish & joylashuv
    document.getElementById("btnSaveReg").addEventListener("click", () => {
      const name = document.getElementById("regNameInput").value.trim();
      const phone = document.getElementById("regPhoneInput").value.trim();
      saveRegistration(name, phone).catch((e) => showToast(e.message, true));
    });
    document.getElementById("btnTgContact").addEventListener("click", () => {
      requestTelegramContact("regPhoneInput", "regNameInput");
    });

    document.getElementById("btnDetectLocation").addEventListener("click", detectGeolocation);
    document.getElementById("latInput").addEventListener("change", () => {
      const lat = parseFloat(document.getElementById("latInput").value);
      const lon = parseFloat(document.getElementById("lonInput").value);
      if (!Number.isNaN(lat) && !Number.isNaN(lon)) setCoordinates(lat, lon, true);
    });
    document.getElementById("lonInput").addEventListener("change", () => {
      const lat = parseFloat(document.getElementById("lonInput").value);
      const lon = parseFloat(document.getElementById("lonInput").value);
      if (!Number.isNaN(lat) && !Number.isNaN(lon)) setCoordinates(lat, lon, true);
    });

    document.getElementById("btnPlaceOrder").addEventListener("click", placeOrder);
    document.getElementById("btnRefreshOrders").addEventListener("click", refreshOrders);

    // Profil saqlash
    document.getElementById("btnSaveProfile").addEventListener("click", () => {
      const name = document.getElementById("profNameInput").value.trim();
      const phone = document.getElementById("profPhoneInput").value.trim();
      saveRegistration(name, phone).catch((e) => showToast(e.message, true));
    });
    document.getElementById("btnProfTgContact").addEventListener("click", () => {
      requestTelegramContact("profPhoneInput", "profNameInput");
    });

    // Admin yangilash tugmalari
    document.getElementById("btnRefreshAdminOrders").addEventListener("click", loadAdminOverview);
    document.getElementById("btnRefreshAdminProducts").addEventListener("click", loadAdminOverview);
    document.getElementById("btnRefreshAdminStats").addEventListener("click", loadAdminOverview);
    document.getElementById("btnRefreshAdminUsers").addEventListener("click", loadAdminOverview);

    document.getElementById("btnAdminSearch").addEventListener("click", () => {
      state.adminSearch = document.getElementById("adminSearchInput").value.trim();
      loadAdminOverview();
    });
    document.getElementById("adminSearchInput").addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        state.adminSearch = e.target.value.trim();
        loadAdminOverview();
      }
    });

    document.getElementById("adminStatusChips").addEventListener("click", (e) => {
      const chip = e.target.closest(".chip-btn");
      if (!chip) return;
      state.adminFilter = chip.dataset.status;
      loadAdminOverview();
    });

    document.getElementById("adminOrdersList").addEventListener("click", async (e) => {
      const btn = e.target.closest("[data-new-status]");
      if (!btn) return;
      const oid = Number(btn.dataset.oid);
      const status = btn.dataset.newStatus;
      btn.disabled = true;
      try {
        await api(`/api/admin/orders/${oid}/status`, {
          method: "POST",
          body: JSON.stringify({ status }),
        });
        haptic("medium");
        showToast(`Buyurtma №${oid} holati yangilandi`);
        await loadAdminOverview();
      } catch (err) {
        showToast(err.message, true);
        btn.disabled = false;
      }
    });

    document.getElementById("adminProductsList").addEventListener("click", async (e) => {
      const toggleBtn = e.target.closest("[data-toggle-pid]");
      if (toggleBtn) {
        const pid = Number(toggleBtn.dataset.togglePid);
        try {
          await api(`/api/admin/products/${pid}/toggle`, { method: "POST", body: "{}" });
          showToast("Mahsulot holati o'zgartirildi ✅");
          await loadAdminOverview();
        } catch (err) {
          showToast(err.message, true);
        }
        return;
      }

      const savePriceBtn = e.target.closest("[data-save-price-pid]");
      if (savePriceBtn) {
        const pid = Number(savePriceBtn.dataset.savePricePid);
        const input = document.getElementById(`priceInput-${pid}`);
        const price = Number(input.value);
        try {
          await api(`/api/admin/products/${pid}/price`, {
            method: "POST",
            body: JSON.stringify({ price }),
          });
          showToast("Narx saqlandi ✅");
          await loadAdminOverview();
        } catch (err) {
          showToast(err.message, true);
        }
      }
    });
  }

  function initTelegramTheme() {
    if (!tg) return;
    try {
      tg.ready();
      tg.expand();
      if (typeof tg.disableVerticalSwipes === "function") {
        tg.disableVerticalSwipes();
      }
      if (typeof tg.enableClosingConfirmation === "function") {
        tg.enableClosingConfirmation();
      }
      if (typeof tg.setHeaderColor === "function") tg.setHeaderColor("#0b0e0c");
      if (typeof tg.setBackgroundColor === "function") tg.setBackgroundColor("#0b0e0c");
    } catch (_) {}
  }

  document.addEventListener("DOMContentLoaded", () => {
    initTelegramTheme();
    bindEvents();
    bootstrap();
  });
})();
