/**
 * MealMatrix – Shared Auth Header Utility
 * =========================================
 * This script handles authentication checks, redirection, and shared UI
 * elements (username display, logout) across all pages.
 *
 * TO USE:
 * <script src="/src/auth-header.js" data-protected="true"></script>
 */

(function () {
    "use strict";

    const API = window.location.protocol === "file:" ? "http://127.0.0.1:5000" : "";
    const IS_PROTECTED = document.currentScript.getAttribute("data-protected") === "true";

    /**
     * Helper: Fetch with retries for transient session issues.
     */
    async function fetchWithRetry(url, opts, attempts = 3, delayMs = 500) {
        for (let i = 0; i < attempts; i++) {
            try {
                const res = await fetch(url, opts);
                if (res.ok) return res;
                if (i === attempts - 1) return res;
            } catch (err) {
                if (i === attempts - 1) throw err;
            }
            await new Promise(r => setTimeout(r, delayMs));
        }
    }

    /**
     * Redirect to login page.
     */
    function redirectToLogin() {
        const loginPath = window.location.pathname.includes("/pages/") ? "login.html" : "pages/login.html";
        window.location.href = (window.location.protocol === "file:" ? "" : "/") + loginPath;
    }

    /**
     * Handle logout.
     */
    async function handleLogout(e) {
        if (e) e.preventDefault();
        try {
            await fetch(API + "/auth/logout", { method: "POST", credentials: "include" });
        } catch { /* ignore */ }
        redirectToLogin();
    }

    /**
     * XSS-safe HTML escaper.
     */
    function escHtml(str) {
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    /**
     * Dynamically fix navigation links.
     * Ensures /pages/* paths work whether on a dev server or local file.
     */
    function fixNavLinks() {
        const isFile = window.location.protocol === "file:";
        const inPages = window.location.pathname.includes("/pages/");
        
        document.querySelectorAll("a[href]").forEach(a => {
            let href = a.getAttribute("href");
            if (href.startsWith("/pages/")) {
                if (isFile) {
                    // file:///.../pages/foo.html
                    // If we are already in /pages/, we don't need the prefix
                    if (inPages) {
                        a.href = href.replace("/pages/", "");
                    } else {
                        a.href = href.substring(1); // remove leading /
                    }
                }
            } else if (href === "/") {
                if (isFile) {
                    a.href = inPages ? "../index.html" : "index.html";
                }
            }
        });
    }

    /**
     * Main initialization.
     */
    async function init() {
        // 1. One-time post-login reload guard
        if (sessionStorage.getItem("mm_just_logged_in") === "1") {
            sessionStorage.removeItem("mm_just_logged_in");
            window.location.reload();
            return;
        }

        // 2. Fix nav links immediately
        fixNavLinks();

        try {
            const res = await fetchWithRetry(API + "/auth/me", { credentials: "include" });
            
            if (res && res.status === 401 && IS_PROTECTED) {
                redirectToLogin();
                return;
            }

            if (res && res.ok) {
                const data = await res.json();
                const u = data.user || data;
                const name = (u.username || u.email || "User").toUpperCase();

                // Update username in header and welcome message (if elements exist)
                const headerEl = document.getElementById("header-username");
                if (headerEl) headerEl.textContent = name;
                
                const welcomeEl = document.getElementById("welcome-name");
                if (welcomeEl) welcomeEl.textContent = name + " !";

                // Update user chip if it exists (for shared header logic)
                const container = document.getElementById("header-auth");
                if (container) {
                    container.innerHTML = "";
                    const chip = document.createElement("span");
                    chip.className = "mm-user-chip";
                    chip.textContent = "👤 " + name;
                    const btn = document.createElement("button");
                    btn.className = "mm-logout-btn";
                    btn.id = "logout-btn";
                    btn.textContent = "Logout";
                    btn.addEventListener("click", handleLogout);
                    container.appendChild(chip);
                    container.appendChild(btn);
                }
            } else if (IS_PROTECTED) {
                redirectToLogin();
            }
        } catch (err) {
            console.error("Auth check failed:", err);
            if (IS_PROTECTED) redirectToLogin();
        }

        // Hook up any logout buttons found by ID
        const logoutBtn = document.getElementById("nav-logout") || document.getElementById("logout-btn");
        if (logoutBtn) {
            logoutBtn.addEventListener("click", handleLogout);
        }
    }

    // Expose a few things globally for page-specific scripts
    window.MealMatrix = {
        apiBase: API,
        handleLogout,
        fetchWithRetry,
        escHtml,
        initAuthHeader: init // Allow manual re-init if needed
    };

    // Run on load
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
