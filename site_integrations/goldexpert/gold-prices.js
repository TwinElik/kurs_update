(function () {
  "use strict";

  var script = document.currentScript;
  var baseUrl = script && script.src
    ? new URL(".", script.src)
    : new URL("/api/", window.location.origin);
  var cacheBucket = Math.floor(Date.now() / 30000);
  var pricesUrl = new URL("current-gold-prices.json?v=" + cacheBucket, baseUrl);
  var tokenPattern = /\[gold_price\s+field=["']([a-z0-9_]+)["']\s*\]/gi;
  var formatter = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 });
  var currentFields = null;
  var replaceScheduled = false;

  function replaceTokens(fields) {
    var roots = document.querySelectorAll("[data-gold-prices-root]");
    if (!roots.length) {
      roots = [document.body];
    }

    Array.prototype.forEach.call(roots, function (root) {
      var walker = document.createTreeWalker(
        root,
        NodeFilter.SHOW_TEXT,
        {
          acceptNode: function (node) {
            var parent = node.parentElement;
            if (!parent || !node.nodeValue || node.nodeValue.indexOf("[gold_price") === -1) {
              return NodeFilter.FILTER_REJECT;
            }
            if (/^(SCRIPT|STYLE|TEXTAREA|INPUT|OPTION)$/i.test(parent.tagName)) {
              return NodeFilter.FILTER_REJECT;
            }
            return NodeFilter.FILTER_ACCEPT;
          },
        }
      );
      var nodes = [];
      var node;
      while ((node = walker.nextNode())) {
        nodes.push(node);
      }

      nodes.forEach(function (textNode) {
        textNode.nodeValue = textNode.nodeValue.replace(tokenPattern, function (token, field) {
          if (!Object.prototype.hasOwnProperty.call(fields, field)) {
            return token;
          }
          return formatter.format(Number(fields[field]));
        });
      });
    });
  }

  function scheduleReplace() {
    if (!currentFields || replaceScheduled) {
      return;
    }

    replaceScheduled = true;
    window.requestAnimationFrame(function () {
      replaceScheduled = false;
      replaceTokens(currentFields);
    });
  }

  function observePageUpdates() {
    if (!document.body || typeof MutationObserver === "undefined") {
      return;
    }

    var observer = new MutationObserver(function () {
      scheduleReplace();
    });

    observer.observe(document.body, {
      childList: true,
      characterData: true,
      subtree: true,
    });
  }

  function loadPrices() {
    fetch(pricesUrl.toString(), {
      method: "GET",
      cache: "no-store",
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    })
      .then(function (response) {
        if (!response.ok) {
          throw new Error("HTTP " + response.status);
        }
        return response.json();
      })
      .then(function (data) {
        if (!data || data.ok !== true || !data.fields) {
          throw new Error("Invalid gold prices response");
        }
        currentFields = data.fields;
        replaceTokens(currentFields);
        observePageUpdates();
        document.dispatchEvent(new CustomEvent("goldprices:loaded", { detail: data }));
      })
      .catch(function (error) {
        console.error("Gold prices were not loaded:", error);
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", loadPrices, { once: true });
  } else {
    loadPrices();
  }
})();
