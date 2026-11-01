// Draw the architecture diagrams on a docs page.
//
// A guide keeps its diagram as mermaid source, so the picture is reviewable in
// the diff and GitHub renders it without anything here. The site needs a
// renderer to do the same, so this module loads one — but only on a page that
// actually has a diagram, because 3.5 MB is not a fair price for prose. The
// runtime is vendored: `script-src 'self'` rules out a CDN.
//
// A diagram whose source no longer parses keeps showing that source rather
// than an empty box, so the failure says where to look.
//
// The markup injected below is mermaid's own SVG output, produced with
// `securityLevel: "strict"`, which sanitizes labels and drops click bindings.
// The only input is a fence in a committed guide, reviewed like any other
// change — the same reason the build refuses raw HTML in a guide.
import mermaid from "./mermaid/mermaid.min.js";

const blocks = Array.from(document.querySelectorAll("pre.mermaid"));
const sources = blocks.map((block) => block.textContent.trim());

function themeName() {
  const light = document.documentElement.getAttribute("data-theme") === "light";
  return light ? "default" : "dark";
}

async function draw() {
  mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: themeName() });
  for (const [index, block] of blocks.entries()) {
    try {
      const { svg } = await mermaid.render(`odi-diagram-${index}`, sources[index]);
      block.innerHTML = svg;
      block.classList.add("is-drawn");
    } catch (error) {
      block.classList.add("is-failed");
      console.warn("a diagram in this guide does not parse", error);
    }
  }
}

await draw();

// The theme toggle repaints the page. A diagram drawn for the other theme keeps
// its old colours until it is drawn again.
new MutationObserver(draw).observe(document.documentElement, {
  attributes: true,
  attributeFilter: ["data-theme"],
});
