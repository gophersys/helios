/**
 * Concord Docs — Auth Gate & Role Filter
 *
 * Docs live on a subdomain (docs.concord.local). The main app sets a
 * concord-auth cookie on the parent domain (.concord.local) on login,
 * so this script can read the JWT and enforce auth + role filtering.
 *
 * 1. No valid JWT cookie → redirect to the main app login page.
 * 2. Valid JWT → decode role, filter nav/tabs by role level.
 */
(function () {
  var COOKIE_NAME = "concord-auth";
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

  function getAuthState() {
    var token = getCookie(COOKIE_NAME);
    if (!token) return null;

    var payload = decodeJwt(token);
    if (!payload) return null;

    // Check expiration
    if (payload.exp && payload.exp * 1000 < Date.now()) {
      return null;
    }

    return { role: payload.role || null };
  }

  function getAppOrigin() {
    // Derive the main app URL from the docs subdomain
    // docs.staging.concord.local → staging.concord.local
    // docs.concord.local → concord.local
    var host = window.location.hostname;
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

  function applyRoleFilter(auth) {
    var userLevel = auth.role ? (ROLE_LEVELS[auth.role] || 0) : 0;

    // Fetch the role manifest generated at build time
    var xhr = new XMLHttpRequest();
    xhr.open("GET", "/role-manifest.json", true);
    xhr.onload = function () {
      if (xhr.status !== 200) return;

      var manifest;
      try {
        manifest = JSON.parse(xhr.responseText);
      } catch (e) {
        return;
      }

      filterElements(".md-nav__link", ".md-nav__item", manifest, userLevel);
      filterElements(".md-tabs__link", ".md-tabs__item", manifest, userLevel);
    };
    xhr.send();
  }

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

  function init() {
    var auth = requireAuth();
    if (!auth) return;
    applyRoleFilter(auth);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  // Re-apply on instant navigation
  if (typeof document$ !== "undefined") {
    document$.subscribe(function () {
      var auth = getAuthState();
      if (!auth) {
        window.location.href = getAppOrigin() + "/login";
        return;
      }
      applyRoleFilter(auth);
    });
  }
})();
