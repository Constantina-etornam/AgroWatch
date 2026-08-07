
// ---------- Auth check & Logout ----------
(function() {
    const user = JSON.parse(localStorage.getItem("agrowatch_user") || "null");
    if (!user) {
        window.location.href = "/login";
        return;
    }
    const welcome = document.getElementById("welcomeText");
    if (welcome) {
        welcome.textContent = `Welcome, ${user.full_name} (${user.user_role})`;
    }
    // Show Dashboard tab only for admin
    const dashTab = document.getElementById("dashboardTab");
    if (dashTab && user.user_role === "admin") {
        dashTab.style.display = "inline-block";
    }
    const logoutBtn = document.getElementById("logoutBtn");
    if (logoutBtn) {
        logoutBtn.addEventListener("click", () => {
            localStorage.removeItem("agrowatch_user");
            window.location.href = "/";
        });
    }
})();


// ---------- Navigation ----------
document.querySelectorAll(".nav-btn").forEach(btn => {
    btn.addEventListener("click", () => {
        document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");

        const section = btn.dataset.section;
        document.getElementById("scan-section").classList.toggle("hidden", section !== "scan");
        document.getElementById("market-section").classList.toggle("hidden", section !== "market");
        document.getElementById("resources-section").classList.toggle("hidden", section !== "resources");

        if (section === "market") loadListings();
        if (section === "resources") loadNews();
    });
});

// ---------- Scan Form ----------
document.getElementById("scanForm").addEventListener("submit", async function(e) {
    e.preventDefault();
    const crop = document.getElementById("crop").value;
    const imageInput = document.getElementById("image");
    const submitBtn = document.getElementById("submitBtn");
    const loading = document.getElementById("loading");
    const results = document.getElementById("results");

    if (!crop || !imageInput.files[0]) {
        alert("Please select a crop and an image.");
        return;
    }

    submitBtn.disabled = true;
    loading.classList.remove("hidden");
    results.classList.add("hidden");
    results.innerHTML = "";

    const formData = new FormData();
    formData.append("crop", crop);
    formData.append("image", imageInput.files[0]);

    try {
        const response = await fetch("/api/scan", { method: "POST", body: formData });
        const data = await response.json();

        if (data.status !== "success") {
            results.innerHTML = `<p style="color:#c62828;">Error: ${data.message || "Unknown error"}</p>`;
            results.classList.remove("hidden");
            return;
        }

        let html = `
            <div class="result-summary">
                <div class="stat"><div class="label">Plants Detected</div><div class="value">${data.total_plants_detected}</div></div>
                <div class="stat"><div class="label">Disease Flags</div><div class="value">${data.disease_flags_raised}</div></div>
            </div>`;

        if (data.detections && data.detections.length > 0) {
            data.detections.forEach((det, idx) => {
                const diag = det.diagnosis || {};
                const severity = diag.severity || "none";
                const condition = (diag.diagnosed_condition || det.class || "unknown").replace(/_/g, " ");
                html += `
                    <div class="detection-card">
                        <h4>Detection #${idx + 1} <span class="badge badge-${severity}">${severity}</span></h4>
                        <p><strong>Class:</strong> ${det.class} &nbsp;|&nbsp; <strong>Confidence:</strong> ${(det.confidence * 100).toFixed(1)}%</p>
                        <p><strong>Condition:</strong> ${condition}</p>
                        <div class="recommendation">${diag.recommendation || "No recommendation available."}</div>
                    </div>`;
            });
        } else {
            html += `<p>No plants detected in the image.</p>`;
        }
        results.innerHTML = html;
        results.classList.remove("hidden");
    } catch (err) {
        results.innerHTML = `<p style="color:#c62828;">Request failed: ${err.message}</p>`;
        results.classList.remove("hidden");
    } finally {
        submitBtn.disabled = false;
        loading.classList.add("hidden");
    }
});

// ---------- Market ----------
document.getElementById("listingForm").addEventListener("submit", async function(e) {
    e.preventDefault();
    const msg = document.getElementById("listingMsg");
    const payload = {
        crop_type: document.getElementById("m_crop").value,
        quantity_kg: document.getElementById("m_qty").value,
        asking_price_ghs: document.getElementById("m_price").value,
        harvest_date: document.getElementById("m_date").value
    };
    try {
        const res = await fetch("/api/market/listings", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        msg.classList.remove("hidden", "success", "error");
        if (data.status === "success") {
            msg.classList.add("success");
            msg.textContent = "Listing posted successfully!";
            document.getElementById("listingForm").reset();
            loadListings();
        } else {
            msg.classList.add("error");
            msg.textContent = data.message || "Failed to create listing";
        }
    } catch (err) {
        msg.classList.remove("hidden");
        msg.classList.add("error");
        msg.textContent = "Request failed: " + err.message;
    }
});

async function loadListings() {
    const container = document.getElementById("listingsContainer");
    container.innerHTML = "<p class='muted'>Loading...</p>";
    try {
        const res = await fetch("/api/market/listings");
        const data = await res.json();
        if (data.status !== "success" || !data.listings.length) {
            container.innerHTML = "<p class='muted'>No active listings yet.</p>";
            return;
        }
        let html = "";
        data.listings.forEach(l => {
            html += `<div class="listing-item">
                <strong>${l.crop_type.toUpperCase()}</strong> — ${l.quantity_kg} kg<br>
                Price: <strong>GHS ${l.asking_price_ghs}</strong> / kg<br>
                Harvest: ${l.harvest_date}
            </div>`;
        });
        container.innerHTML = html;
    } catch (err) {
        container.innerHTML = `<p class='muted'>Failed to load listings.</p>`;
    }
}
document.getElementById("refreshListings").addEventListener("click", loadListings);

// ---------- Resources ----------
document.querySelectorAll(".res-tab").forEach(tab => {
    tab.addEventListener("click", () => {
        document.querySelectorAll(".res-tab").forEach(t => t.classList.remove("active"));
        tab.classList.add("active");
        const target = tab.dataset.res;
        ["news", "opportunities", "pesticides", "shops"].forEach(id => {
            document.getElementById("res-" + id).classList.toggle("hidden", id !== target);
        });
        if (target === "news") loadNews();
        if (target === "opportunities") loadOpportunities();
        if (target === "pesticides") loadPesticides();
        if (target === "shops") loadShops();
    });
});

async function loadNews() {
    const panel = document.getElementById("res-news");
    panel.innerHTML = "<p class='muted'>Loading live news...</p>";
    try {
        const res = await fetch("/api/resources/news");
        const data = await res.json();
        if (data.status !== "success") {
            panel.innerHTML = "<p class='muted'>Could not load news.</p>";
            return;
        }
        let html = "";
        data.news.forEach(n => {
            html += `<div class="news-item">
                <a href="${n.link}" target="_blank" rel="noopener">${n.title}</a>
                <div class="news-meta">${n.source} • ${n.published}</div>
            </div>`;
        });
        panel.innerHTML = html || "<p class='muted'>No headlines available right now.</p>";
    } catch (err) {
        panel.innerHTML = "<p class='muted'>Failed to load news.</p>";
    }
}

async function loadOpportunities() {
    const panel = document.getElementById("res-opportunities");
    panel.innerHTML = "<p class='muted'>Loading...</p>";
    try {
        const res = await fetch("/api/resources/opportunities");
        const data = await res.json();
        let html = "";
        data.opportunities.forEach(o => {
            html += `<div class="opp-item">
                <strong>${o.title}</strong>
                <p>${o.description}</p>
                ${o.link ? `<a href="${o.link}" target="_blank">Learn more</a>` : ""}
            </div>`;
        });
        panel.innerHTML = html;
    } catch (err) {
        panel.innerHTML = "<p class='muted'>Failed to load opportunities.</p>";
    }
}

async function loadPesticides() {
    const panel = document.getElementById("res-pesticides");
    panel.innerHTML = "<p class='muted'>Loading...</p>";
    try {
        const res = await fetch("/api/resources/pesticides");
        const data = await res.json();
        let html = "";
        data.education.forEach(e => {
            html += `<div class="edu-card"><h4>${e.title}</h4><ul>`;
            e.points.forEach(p => html += `<li>${p}</li>`);
            html += `</ul></div>`;
        });
        panel.innerHTML = html;
    } catch (err) {
        panel.innerHTML = "<p class='muted'>Failed to load education content.</p>";
    }
}

async function loadShops() {
    const panel = document.getElementById("res-shops");
    panel.innerHTML = "<p class='muted'>Loading...</p>";
    try {
        const res = await fetch("/api/resources/shops");
        const data = await res.json();
        let html = "";
        data.shops.forEach(s => {
            html += `<div class="shop-item">
                <strong>${s.name}</strong><br>
                📍 ${s.location}<br>
                📞 ${s.contact}<br>
                <small>${s.notes}</small>
                ${s.maps ? `<br><a href="${s.maps}" target="_blank">View on Map</a>` : ""}
            </div>`;
        });
        if (data.note) html += `<p class="muted" style="margin-top:1rem;">${data.note}</p>`;
        panel.innerHTML = html;
    } catch (err) {
        panel.innerHTML = "<p class='muted'>Failed to load shops.</p>";
    }
}


// ---------- Local Markets ----------
async function loadMarkets() {
    const container = document.getElementById("marketsContainer");
    if (!container) return;
    container.innerHTML = "<p class='muted'>Loading markets...</p>";
    try {
        const res = await fetch("/api/market/local-markets");
        const data = await res.json();
        if (data.status !== "success") {
            container.innerHTML = "<p class='muted'>Could not load markets.</p>";
            return;
        }
        let html = "";
        data.markets.forEach(m => {
            html += `<div class="listing-item">
                <strong>${m.name}</strong><br>
                📍 ${m.location} • ${m.type}<br>
                <small>${m.notes}</small>
                ${m.maps ? `<br><a href="${m.maps}" target="_blank">View on Map</a>` : ""}
            </div>`;
        });
        if (data.note) {
            html += `<p class="muted" style="margin-top:0.8rem;">${data.note}</p>`;
        }
        container.innerHTML = html;
    } catch (err) {
        container.innerHTML = "<p class='muted'>Failed to load markets.</p>";
    }
}

document.addEventListener("DOMContentLoaded", () => {
    const btn = document.getElementById("refreshMarkets");
    if (btn) btn.addEventListener("click", loadMarkets);
});


// ---------- Dashboard (Admin) ----------
async function loadDashboard() {
    try {
        const res = await fetch("/api/dashboard");
        const data = await res.json();
        if (data.status !== "success") return;

        document.getElementById("statScans").textContent = data.summary.total_scans;
        document.getElementById("statPlants").textContent = data.summary.total_plants_detected;
        document.getElementById("statDiseases").textContent = data.summary.total_disease_flags;
        document.getElementById("statListings").textContent = data.summary.active_listings;

        // Recent scans
        const recentBox = document.getElementById("dashRecentScans");
        if (data.recent_scans.length === 0) {
            recentBox.innerHTML = "<p class='muted'>No scans yet.</p>";
        } else {
            let html = "";
            data.recent_scans.forEach(s => {
                html += `<div class="listing-item">
                    Scan #${s.scan_id} — ${s.scan_date}<br>
                    Plants: ${s.total_plants_detected} | Disease flags: ${s.disease_flags_raised}
                </div>`;
            });
            recentBox.innerHTML = html;
        }

        // Disease breakdown
        const diseaseBox = document.getElementById("dashDiseases");
        if (data.disease_breakdown.length === 0) {
            diseaseBox.innerHTML = "<p class='muted'>No disease records yet.</p>";
        } else {
            let html = "";
            data.disease_breakdown.forEach(d => {
                html += `<div class="listing-item">
                    <strong>${d.diagnosed_condition.replace(/_/g, " ")}</strong> — ${d.count} case(s)
                </div>`;
            });
            diseaseBox.innerHTML = html;
        }
    } catch (err) {
        console.error("Dashboard load failed", err);
    }
}

// Extend navigation to handle dashboard
document.querySelectorAll(".nav-btn").forEach(btn => {
    btn.addEventListener("click", () => {
        const section = btn.dataset.section;
        const dashSec = document.getElementById("dashboard-section");
        if (dashSec) {
            dashSec.classList.toggle("hidden", section !== "dashboard");
        }
        if (section === "dashboard") loadDashboard();
    });
});


// ---------- Scan History ----------
async function loadHistory() {
    const container = document.getElementById("historyContainer");
    if (!container) return;
    container.innerHTML = "<p class='muted'>Loading...</p>";
    try {
        const res = await fetch("/api/history");
        const data = await res.json();
        if (data.status !== "success" || !data.history.length) {
            container.innerHTML = "<p class='muted'>No scans yet. Upload an image to get started.</p>";
            return;
        }
        let html = "";
        data.history.forEach(h => {
            const date = h.scan_date || "Unknown date";
            const crop = h.crop_type || "crop";
            html += `<div class="listing-item">
                <strong>Scan #${h.scan_id}</strong> — ${date}<br>
                Crop: ${crop} | Plants: ${h.total_plants_detected} | 
                Disease flags: <strong>${h.disease_flags_raised}</strong>
            </div>`;
        });
        container.innerHTML = html;
    } catch (err) {
        container.innerHTML = "<p class='muted'>Failed to load history.</p>";
    }
}

document.addEventListener("DOMContentLoaded", () => {
    const btn = document.getElementById("refreshHistory");
    if (btn) btn.addEventListener("click", loadHistory);
});

// Make sure History section toggles correctly
document.querySelectorAll(".nav-btn").forEach(btn => {
    btn.addEventListener("click", () => {
        const section = btn.dataset.section;
        const histSec = document.getElementById("history-section");
        if (histSec) {
            histSec.classList.toggle("hidden", section !== "history");
        }
        if (section === "history") loadHistory();
    });
});


// ---------- Role-based tabs + default view ----------
(function applyRoleAccess() {
    const user = JSON.parse(localStorage.getItem("agrowatch_user") || "null");
    if (!user) return;

    const role = user.user_role || "farmer";

    // What each role can see
    const access = {
        farmer: ["scan", "history", "market", "resources"],
        buyer:  ["market", "resources"],
        expert: ["resources", "history", "scan"],
        admin:  ["dashboard", "scan", "history", "market", "resources"]
    };

    const allowed = access[role] || access.farmer;

    // Default starting tab
    const defaults = {
        farmer: "scan",
        buyer: "market",
        expert: "resources",
        admin: "dashboard"
    };
    const defaultTab = defaults[role] || "scan";

    // Show / hide nav buttons
    document.querySelectorAll(".nav-btn").forEach(btn => {
        const section = btn.dataset.section;
        if (allowed.includes(section)) {
            btn.style.display = "";
        } else {
            btn.style.display = "none";
        }
        btn.classList.remove("active");
    });

    // Hide all sections first
    document.querySelectorAll("main section").forEach(s => s.classList.add("hidden"));

    // Activate default tab
    setTimeout(() => {
        const btn = document.querySelector(`.nav-btn[data-section="${defaultTab}"]`);
        const section = document.getElementById(defaultTab + "-section");
        if (btn) btn.classList.add("active");
        if (section) section.classList.remove("hidden");

        if (defaultTab === "dashboard" && typeof loadDashboard === "function") loadDashboard();
        if (defaultTab === "history" && typeof loadHistory === "function") loadHistory();
        if (defaultTab === "market" && typeof loadListings === "function") loadListings();
        if (defaultTab === "resources" && typeof loadNews === "function") loadNews();
    }, 120);
})();


// ---------- Image source: Upload or Camera ----------
(function setupImageSource() {
    const fileInput = document.getElementById("image");
    const btnUpload = document.getElementById("btnUpload");
    const btnCamera = document.getElementById("btnCamera");
    const previewBox = document.getElementById("imagePreview");
    const previewImg = document.getElementById("previewImg");
    const previewName = document.getElementById("previewName");

    if (!fileInput || !btnUpload || !btnCamera) return;

    function showPreview(file) {
        if (!file) return;
        const url = URL.createObjectURL(file);
        previewImg.src = url;
        previewName.textContent = file.name || "Captured photo";
        previewBox.style.display = "block";
    }

    btnUpload.addEventListener("click", () => {
        fileInput.removeAttribute("capture");
        fileInput.accept = "image/*";
        fileInput.click();
    });

    btnCamera.addEventListener("click", () => {
        // Prefer rear camera on phones
        fileInput.setAttribute("capture", "environment");
        fileInput.accept = "image/*";
        fileInput.click();
    });

    fileInput.addEventListener("change", () => {
        if (fileInput.files && fileInput.files[0]) {
            showPreview(fileInput.files[0]);
        }
    });
})();


// ---------- Home section helpers ----------
document.addEventListener("DOMContentLoaded", () => {
    const goLogin = document.getElementById("goLoginFromHome");
    if (goLogin) {
        goLogin.addEventListener("click", () => {
            const loginBtn = document.querySelector('.nav-btn[data-section="login"]') ||
                             document.getElementById("loginTab");
            if (loginBtn) loginBtn.click();
            else {
                document.querySelectorAll("main section").forEach(s => s.classList.add("hidden"));
                const loginSec = document.getElementById("login-section");
                if (loginSec) loginSec.classList.remove("hidden");
            }
        });
    }
    // Home quick links that use data-section
    document.querySelectorAll('#home-section .nav-btn[data-section]').forEach(btn => {
        btn.addEventListener("click", () => {
            const target = btn.dataset.section;
            const navBtn = document.querySelector(`.nav-btn[data-section="${target}"]`);
            if (navBtn) navBtn.click();
        });
    });
});
