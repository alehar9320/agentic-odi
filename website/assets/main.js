// Progressive enhancement for the site.
//
// The page is complete and readable without this file. Everything here is an
// addition: tabs that switch panels, copy buttons that copy, and sections
// that fade up once as they come into view.
//
// The reveal is opt-in: the hidden state is scoped to a class this script
// adds, so a reader without JavaScript never loses anything.

(function () {
  "use strict";

  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)");

  /* ---------------------------------------------------------------- */
  /* Copy buttons                                                      */
  /* ---------------------------------------------------------------- */

  var live = document.createElement("span");
  live.setAttribute("aria-live", "polite");
  live.setAttribute("role", "status");
  live.className = "sr-only";
  document.body.appendChild(live);

  function codeFor(button) {
    var scope = button.closest(".codeblock, .endpoint__url, pre");
    if (!scope) return null;
    var codes = scope.querySelectorAll("code");
    for (var i = 0; i < codes.length; i += 1) {
      var code = codes[i];
      if (code.contains(button) || button.contains(code)) continue;
      return code;
    }
    return null;
  }

  function legacyCopy(text) {
    var area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "readonly");
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    var copied = false;
    try {
      copied = document.execCommand("copy");
    } catch (error) {
      copied = false;
    }
    document.body.removeChild(area);
    return copied;
  }

  function announce(message) {
    live.textContent = "";
    window.setTimeout(function () {
      live.textContent = message;
    }, 30);
  }

  document.querySelectorAll("[data-copy]").forEach(function (button) {
    button.addEventListener("click", function () {
      var code = codeFor(button);
      if (!code) return;
      var text = code.textContent;

      var done = function (ok) {
        if (!ok) {
          announce("Copy failed. Select the text and copy it manually.");
          return;
        }
        var original = button.textContent;
        button.textContent = "Copied";
        announce("Copied to clipboard");
        window.setTimeout(function () {
          button.textContent = original;
        }, 1500);
      };

      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(
          function () {
            done(true);
          },
          function () {
            done(legacyCopy(text));
          }
        );
      } else {
        done(legacyCopy(text));
      }
    });
  });

  /* ---------------------------------------------------------------- */
  /* Tabs                                                              */
  /* ---------------------------------------------------------------- */

  document.querySelectorAll("[data-tabs]").forEach(function (group) {
    var tabs = Array.prototype.slice.call(group.querySelectorAll('[role="tab"]'));
    if (!tabs.length) return;

    function select(tab, focus) {
      tabs.forEach(function (other) {
        var selected = other === tab;
        var panel = document.getElementById(other.getAttribute("aria-controls"));
        other.setAttribute("aria-selected", selected ? "true" : "false");
        other.setAttribute("tabindex", selected ? "0" : "-1");
        if (panel) panel.hidden = !selected;
      });
      if (focus) tab.focus();
    }

    tabs.forEach(function (tab, index) {
      tab.addEventListener("click", function () {
        select(tab, false);
      });
      tab.addEventListener("keydown", function (event) {
        var next = null;
        if (event.key === "ArrowRight" || event.key === "ArrowDown") {
          next = tabs[(index + 1) % tabs.length];
        } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
          next = tabs[(index - 1 + tabs.length) % tabs.length];
        } else if (event.key === "Home") {
          next = tabs[0];
        } else if (event.key === "End") {
          next = tabs[tabs.length - 1];
        }
        if (next) {
          event.preventDefault();
          select(next, true);
        }
      });
    });
  });

  /* ---------------------------------------------------------------- */
  /* Scroll reveal                                                     */
  /* ---------------------------------------------------------------- */

  var revealTargets = document.querySelectorAll("[data-reveal]");

  if ("IntersectionObserver" in window && revealTargets.length) {
    var root = document.documentElement;
    root.classList.add("js-reveal");

    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        });
      },
      { threshold: 0.15, rootMargin: "0px 0px -40px 0px" }
    );

    revealTargets.forEach(function (target) {
      observer.observe(target);
    });
  }

  if (reduced.matches) {
    document.documentElement.classList.add("reduced-motion");
  }
})();
