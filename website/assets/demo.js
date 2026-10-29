// The scripted Living Studio demo.
//
// The page ships a complete, static transcript of the three exchanges — that
// is what a reader without JavaScript sees. This script takes over from
// there: it hides the transcript, shows the live thread, and replays one
// exchange at a time.
//
// The exchanges themselves are never re-rendered here. The script clones the
// markup the server already produced, so the card a visitor sees is exactly
// the card the page shipped with.

(function () {
  "use strict";

  var demo = document.querySelector("[data-demo]");
  if (!demo) return;

  var transcript = demo.querySelector("[data-demo-transcript]");
  var live = demo.querySelector("[data-demo-live]");
  var thread = demo.querySelector("[data-demo-thread]");
  var input = demo.querySelector(".demo__input");
  var send = demo.querySelector("[data-demo-send]");
  var chips = demo.querySelectorAll("[data-demo-chip]");

  if (!transcript || !live || !thread) return;

  var exchanges = Array.prototype.slice.call(
    transcript.querySelectorAll(".demo__exchange")
  );
  if (!exchanges.length) return;

  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
  var TYPING_MS = 620;

  function current() {
    return exchanges[0];
  }

  function typingIndicator() {
    var el = document.createElement("div");
    el.className = "demo__typing";
    el.innerHTML = '<span class="demo__avatar" aria-hidden="true"></span>' +
      '<span class="typing__dots" aria-hidden="true"><i></i><i></i><i></i></span>' +
      '<span class="sr-only">The agent is typing</span>';
    return el;
  }

  function show(index) {
    var exchange = exchanges[index] || current();
    thread.replaceChildren();

    var node = exchange.cloneNode(true);
    var assistant = node.querySelector(".demo__msg--assistant");
    if (assistant) assistant.classList.add("is-pending");
    thread.appendChild(node);

    if (reduced.matches) {
      if (assistant) assistant.classList.remove("is-pending");
      return;
    }

    var typing = typingIndicator();
    thread.appendChild(typing);
    window.setTimeout(function () {
      typing.remove();
      if (assistant) assistant.classList.remove("is-pending");
    }, TYPING_MS);
  }

  // A typed prompt picks the exchange it most resembles. There is no model
  // here and there is no network call — the demo is a fixed script.
  function matchIndex(text) {
    var words = text
      .toLowerCase()
      .split(/[^a-z0-9]+/)
      .filter(function (word) { return word.length > 2; });
    if (!words.length) return 0;

    var best = 0;
    var bestScore = -1;
    exchanges.forEach(function (exchange, index) {
      var prompt = exchange.querySelector(".demo__bubble--user");
      var haystack = (prompt ? prompt.textContent : "").toLowerCase();
      var score = 0;
      words.forEach(function (word) {
        if (haystack.indexOf(word) !== -1) score += 1;
      });
      if (score > bestScore) {
        bestScore = score;
        best = index;
      }
    });
    return best;
  }

  function sendText(text) {
    var value = (text || "").trim();
    if (!value) return;
    show(matchIndex(value));
    if (input) {
      input.value = "";
      input.style.height = "auto";
    }
  }

  chips.forEach(function (chip) {
    chip.addEventListener("click", function () {
      var index = parseInt(chip.getAttribute("data-exchange"), 10) || 0;
      show(index);
    });
  });

  if (send) {
    send.addEventListener("click", function () {
      sendText(input ? input.value : "");
    });
  }

  if (input) {
    input.addEventListener("keydown", function (event) {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendText(input.value);
      }
    });
    input.addEventListener("input", function () {
      input.style.height = "auto";
      input.style.height = input.scrollHeight + "px";
    });
  }

  // Take over from the static transcript.
  transcript.hidden = true;
  live.hidden = false;
  show(0);
})();
