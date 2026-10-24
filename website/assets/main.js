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
  /* Docs search                                                       */
  /* ---------------------------------------------------------------- */

  var search = document.querySelector("[data-search]");

  if (search) {
    var searchInput = search.querySelector("[data-search-input]");
    var searchResults = search.querySelector("[data-search-results]");
    var searchHint = search.querySelector("[data-search-hint]");
    var searchEntries = null;
    var searchMatches = [];
    var searchActive = -1;
    var siteUrl = search.getAttribute("data-site-url") || "/";
    var indexUrl = search.getAttribute("data-index-url");

    function loadSearchIndex() {
      if (searchEntries) return Promise.resolve(searchEntries);
      return fetch(indexUrl)
        .then(function (response) {
          return response.json();
        })
        .then(function (entries) {
          searchEntries = Array.isArray(entries) ? entries : [];
          return searchEntries;
        })
        .catch(function () {
          searchEntries = [];
          return searchEntries;
        });
    }

    function subsequence(needle, haystack) {
      var index = 0;
      for (var i = 0; i < haystack.length && index < needle.length; i += 1) {
        if (haystack.charAt(i) === needle.charAt(index)) index += 1;
      }
      return index === needle.length;
    }

    function fuzzyScore(entry, query) {
      if (!query) return 1;
      var title = entry.title.toLowerCase();
      var excerpt = (entry.excerpt || "").toLowerCase();
      var tokens = query.split(/\s+/).filter(Boolean);
      var score = 0;
      for (var i = 0; i < tokens.length; i += 1) {
        var token = tokens[i];
        if (title.indexOf(token) === 0) score += 40;
        else if (title.indexOf(token) !== -1) score += 25;
        else if (excerpt.indexOf(token) !== -1) score += 10;
        else if (subsequence(token, title + " " + excerpt)) score += 4;
        else return 0;
      }
      return score;
    }

    function renderSearch(query) {
      var cleaned = query.trim();
      var ranked = searchEntries
        .map(function (entry) {
          return { entry: entry, score: fuzzyScore(entry, cleaned.toLowerCase()) };
        })
        .filter(function (item) {
          return item.score > 0;
        })
        .sort(function (a, b) {
          return b.score - a.score || a.entry.title.localeCompare(b.entry.title);
        })
        .slice(0, 8);

      searchMatches = ranked.map(function (item) {
        return item.entry;
      });
      searchActive = searchMatches.length ? 0 : -1;
      searchResults.textContent = "";

      if (!searchMatches.length) {
        searchHint.textContent = cleaned
          ? "No page matches \u201c" + cleaned + "\u201d."
          : "Type to search every guide and reference page.";
        return;
      }

      searchHint.textContent =
        searchMatches.length + " page" + (searchMatches.length === 1 ? "" : "s") + ".";

      searchMatches.forEach(function (entry, index) {
        var item = document.createElement("li");
        var link = document.createElement("a");
        link.className = "search__result" + (index === searchActive ? " is-active" : "");
        link.href = siteUrl + entry.url;

        var title = document.createElement("span");
        title.className = "search__result-title";
        title.textContent = entry.title;

        var excerpt = document.createElement("span");
        excerpt.className = "search__result-excerpt";
        excerpt.textContent = entry.excerpt || "";

        link.appendChild(title);
        link.appendChild(excerpt);
        item.appendChild(link);
        searchResults.appendChild(item);
      });
    }

    function moveSearch(delta) {
      if (!searchMatches.length) return;
      searchActive = (searchActive + delta + searchMatches.length) % searchMatches.length;
      var links = searchResults.querySelectorAll("a");
      for (var i = 0; i < links.length; i += 1) {
        links[i].classList.toggle("is-active", i === searchActive);
      }
      if (links[searchActive]) links[searchActive].scrollIntoView({ block: "nearest" });
    }

    function openSearch() {
      search.hidden = false;
      document.documentElement.classList.add("search-open");
      searchInput.value = "";
      searchInput.focus();
      loadSearchIndex().then(function () {
        renderSearch("");
      });
    }

    function closeSearch() {
      search.hidden = true;
      document.documentElement.classList.remove("search-open");
    }

    document.querySelectorAll("[data-search-open]").forEach(function (button) {
      button.addEventListener("click", openSearch);
    });

    document.querySelectorAll("[data-search-close]").forEach(function (button) {
      button.addEventListener("click", closeSearch);
    });

    searchInput.addEventListener("input", function () {
      loadSearchIndex().then(function () {
        renderSearch(searchInput.value);
      });
    });

    searchInput.addEventListener("keydown", function (event) {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        moveSearch(1);
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        moveSearch(-1);
      } else if (event.key === "Enter") {
        var active = searchResults.querySelector("a.is-active");
        if (active) {
          event.preventDefault();
          window.location.href = active.href;
        }
      }
    });

    document.addEventListener("keydown", function (event) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        if (search.hidden) openSearch();
        else closeSearch();
      } else if (event.key === "Escape" && !search.hidden) {
        closeSearch();
      }
    });
  }

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
