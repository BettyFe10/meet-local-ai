import { test } from "node:test";
import assert from "node:assert/strict";
import { filterMeetings } from "../../extension/lib/ui.js";

const M = [
  { id: "a", title: "Riunione commerciale", date: "2026-09-27", created_at: "2026-09-27T10:30:00+02:00", status: "completed" },
  { id: "b", title: "Budget social", date: "2026-10-01", created_at: "2026-10-01T09:00:00+02:00", status: "transcribing" },
  { id: "c", title: "Prova audio", date: "2026-10-01", created_at: "2026-10-01T19:09:00+02:00", status: "error" },
  { id: "d", title: "Daily", date: "2026-10-02", created_at: "2026-10-02T09:00:00+02:00", status: "transcribed" },
];
const ids = (l) => l.map((m) => m.id).join("");

test("senza filtri restituisce tutto", () => assert.equal(ids(filterMeetings(M)), "abcd"));
test("ricerca per titolo, senza distinzione maiuscole", () => assert.equal(ids(filterMeetings(M, "BUDGET")), "b"));
test("ricerca per data ISO e italiana", () => {
  assert.equal(ids(filterMeetings(M, "2026-10-01")), "bc");
  assert.equal(ids(filterMeetings(M, "27/09")), "a");
});
test("filtro per stato", () => {
  assert.equal(ids(filterMeetings(M, "", "done")), "ad");
  assert.equal(ids(filterMeetings(M, "", "busy")), "b");
  assert.equal(ids(filterMeetings(M, "", "problem")), "c");
});
test("filtri combinati", () => assert.equal(ids(filterMeetings(M, "prova", "done")), ""));
