/**
 * Concord Docs — Auth Gate & Role Filter
 *
 * Works in two modes:
 *
 * Production/Staging: Docs live on a subdomain (docs.concord.local). The main
 * app sets a concord-auth cookie on the parent domain. This script reads the
 * JWT from the cookie.
 *
 * Development: Docs run on localhost:4000, app on localhost:4200. No shared
 * cookies. The app passes the JWT as a ?token= URL parameter. This script
 * stores it in sessionStorage for subsequent page loads.
 *
 * Flow:
 *   1. Read JWT from: URL param → sessionStorage → cookie
 *   2. No JWT → redirect to main app login
 *   3. Valid JWT → decode role, filter nav/tabs by min_role
 */
(function () {
  var COOKIE_NAME = "concord-auth";
  var STORAGE_KEY = "concord-docs-token";
  var ROLE_LEVELS = { OPERATOR: 1, DEVELOPER: 2, MAINTAINER: 3, ADMIN: 4 };

  function getCookie(name) {
    var match = document.cookie.match(new RegExp("(^| )" + name + "=([^;]+)"));
    return match ? match[2] : null;
  }

  function decodeJwt(token) {
    try {
      var parts = token.split(".");
      if (parts.length !== 3) return null;
      return JSON.parse(atob(parts[1]));
    } catch (e) {
      return null;
    }
  }

  function getToken() {
    // 1. Check URL param (app passes token when opening docs)
    var params = new URLSearchParams(window.location.search);
    var urlToken = params.get("token");
    if (urlToken) {
      // Store for subsequent navigations and strip from URL
      try { sessionStorage.setItem(STORAGE_KEY, urlToken); } catch (e) {}
      var clean = window.location.pathname + window.location.hash;
      window.history.replaceState(null, "", clean);
      return urlToken;
    }

    // 2. Check sessionStorage (dev mode, subsequent pages)
    try {
      var stored = sessionStorage.getItem(STORAGE_KEY);
      if (stored) return stored;
    } catch (e) {}

    // 3. Check cookie (staging/production subdomain mode)
    return getCookie(COOKIE_NAME);
  }

  function getAuthState() {
    var token = getToken();
    if (!token) return null;

    var payload = decodeJwt(token);
    if (!payload) return null;

    // Check expiration
    if (payload.exp && payload.exp * 1000 < Date.now()) {
      try { sessionStorage.removeItem(STORAGE_KEY); } catch (e) {}
      return null;
    }

    return { role: payload.role || null, token: token };
  }

  function getAppOrigin() {
    var host = window.location.hostname;
    // Dev mode: docs on localhost:4000, app on localhost:4200
    if (host === "localhost" || host === "127.0.0.1") {
      return window.location.protocol + "//" + host + ":4200";
    }
    // Production: docs.concord.local → concord.local
    if (host.startsWith("docs.")) {
      host = host.substring(5);
    }
    return window.location.protocol + "//" + host;
  }

  function requireAuth() {
    var auth = getAuthState();
    if (!auth) {
      window.location.href = getAppOrigin() + "/login";
      return null;
    }
    return auth;
  }

  // applyRoleFilter is now applyRoleFilterCached (defined below init)

  function filterElements(linkSelector, containerSelector, manifest, userLevel) {
    var links = document.querySelectorAll(linkSelector);
    links.forEach(function (link) {
      var href = link.getAttribute("href");
      if (!href) return;

      var path = normalizePath(href);
      var pageInfo = manifest.pages[path];
      if (pageInfo && pageInfo.min_level > userLevel) {
        var container = link.closest(containerSelector);
        if (container) container.style.display = "none";
      }
    });
  }

  /**
   * Filter inline content links — hide table rows and paragraphs
   * that only contain restricted links the user can't access.
   */
  function filterContentLinks(manifest, userLevel) {
    // Hide table rows where every link is restricted
    document.querySelectorAll(".md-content table tr").forEach(function (row) {
      var links = row.querySelectorAll("a[href]");
      if (links.length === 0) return;
      var allRestricted = true;
      links.forEach(function (link) {
        var path = normalizePath(link.getAttribute("href"));
        var info = manifest.pages[path];
        if (!info || info.min_level <= userLevel) allRestricted = false;
      });
      if (allRestricted) row.style.display = "none";
    });

    // Disable restricted links in body text — replace with plain text
    document.querySelectorAll(".md-content a[href]").forEach(function (link) {
      var path = normalizePath(link.getAttribute("href"));
      var info = manifest.pages[path];
      if (info && info.min_level > userLevel) {
        var span = document.createElement("span");
        span.textContent = link.textContent;
        span.style.opacity = "0.4";
        span.title = "Requires " + info.min_role + " access";
        link.parentNode.replaceChild(span, link);
      }
    });
  }

  /**
   * Guard: if the current page is restricted, redirect to home.
   */
  function guardCurrentPage(manifest, userLevel) {
    var path = window.location.pathname;
    if (!path.endsWith("/")) path += "/";
    var info = manifest.pages[path];
    if (info && info.min_level > userLevel) {
      window.location.href = "/?access_denied=" + encodeURIComponent(path);
    }
  }

  function normalizePath(href) {
    try {
      var url = new URL(href, window.location.origin);
      var path = url.pathname;
      if (!path.endsWith("/")) path += "/";
      return path;
    } catch (e) {
      var a = document.createElement("a");
      a.href = href;
      var path = a.pathname;
      if (!path.endsWith("/")) path += "/";
      return path;
    }
  }

  function showRoleBadge(role, level) {
    if (!role) return;
    var existing = document.getElementById("concord-role-badge");
    if (existing) existing.remove();

    var colors = { OPERATOR: "#e67e22", DEVELOPER: "#3498db", MAINTAINER: "#9b59b6", ADMIN: "#e74c3c" };
    var badge = document.createElement("div");
    badge.id = "concord-role-badge";
    badge.style.cssText = "position:fixed;bottom:12px;right:12px;z-index:9999;padding:4px 10px;border-radius:4px;font-size:11px;font-weight:600;letter-spacing:0.5px;color:#fff;background:" + (colors[role] || "#666");
    badge.textContent = role;
    document.body.appendChild(badge);
  }

  // Cache the manifest so we don't re-fetch on every apply
  var _cachedManifest = null;

  function applyRoleFilterCached(auth) {
    if (_cachedManifest) {
      applyFilterWithManifest(auth, _cachedManifest);
      return;
    }
    var xhr = new XMLHttpRequest();
    xhr.open("GET", "/role-manifest.json", true);
    xhr.onload = function () {
      if (xhr.status !== 200) return;
      try { _cachedManifest = JSON.parse(xhr.responseText); } catch (e) { return; }
      applyFilterWithManifest(auth, _cachedManifest);
    };
    xhr.send();
  }

  function applyFilterWithManifest(auth, manifest) {
    var userLevel = auth.role ? (ROLE_LEVELS[auth.role] || 0) : 0;
    showRoleBadge(auth.role, userLevel);
    guardCurrentPage(manifest, userLevel);
    filterElements(".md-nav__link", ".md-nav__item", manifest, userLevel);
    filterElements(".md-tabs__link", ".md-tabs__item", manifest, userLevel);
    filterContentLinks(manifest, userLevel);
  }

  function init() {
    var auth = requireAuth();
    if (!auth) return;
    applyRoleFilterCached(auth);

    // Re-apply after short delay to catch late-rendered elements
    setTimeout(function () {
      var a = getAuthState();
      if (a) applyRoleFilterCached(a);
    }, 500);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  // Re-apply on instant navigation (Material theme)
  if (typeof document$ !== "undefined") {
    document$.subscribe(function () {
      var auth = getAuthState();
      if (!auth) {
        window.location.href = getAppOrigin() + "/login";
        return;
      }
      applyRoleFilterCached(auth);
      // Material re-renders async, so re-apply after settle
      setTimeout(function () {
        var a = getAuthState();
        if (a) applyRoleFilterCached(a);
      }, 300);
    });
  }
})();
