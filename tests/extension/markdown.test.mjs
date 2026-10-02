import { test } from "node:test";
import assert from "node:assert/strict";

// DOM minimo per provare renderMarkdownLite senza browser
class Node_ { constructor(tag) { this.tag = tag; this.children = []; this.attrs = {}; }
  append(...c) { for (const x of c.flat()) this.children.push(x); }
  setAttribute(k, v) { this.attrs[k] = v; } addEventListener() {}
  get text() { return this.children.map((c) => (typeof c === "string" ? c : c.text)).join(""); } }
globalThis.Node = Node_;
globalThis.document = { createElement: (t) => new Node_(t), createDocumentFragment: () => new Node_("#frag") };
const { renderMarkdownLite } = await import("../../extension/lib/ui.js");

test("elenchi, grassetto e paragrafi; nessun HTML interpretato", () => {
  const f = renderMarkdownLite("- primo **importante**\n* secondo\n\nTesto <script>alert(1)</script>\n1. numerato");
  assert.deepEqual(f.children.map((c) => c.tag), ["ul", "p", "ul"]);
  assert.equal(f.children[0].children.length, 2);
  assert.equal(f.children[0].children[0].children[1].tag, "strong");
  assert.equal(f.children[1].text, "Testo <script>alert(1)</script>");   // resta testo, non diventa markup
  assert.equal(f.children[2].children[0].text, "numerato");
});

test("testo vuoto → nessun nodo", () => {
  assert.equal(renderMarkdownLite("").children.length, 0);
});
