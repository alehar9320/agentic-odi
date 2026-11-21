import { describe, expect, it } from "vitest";
import { parseRoute, routeToPath, withSearch, type Route } from "./routes";

describe("parseRoute", () => {
  it("reads the home address", () => {
    expect(parseRoute("/")).toEqual({ name: "home", search: "" });
  });

  it("reads a thread", () => {
    expect(parseRoute("/t/c-8f21")).toEqual({
      name: "thread",
      threadId: "c-8f21",
      search: "",
    });
  });

  it("reads a thread panel", () => {
    expect(parseRoute("/t/c-8f21/landscape")).toEqual({
      name: "threadPanel",
      threadId: "c-8f21",
      panel: "landscape",
      search: "",
    });
  });

  it("reads a panel subject", () => {
    expect(parseRoute("/t/c-8f21/landscape/outcome/O-12")).toEqual({
      name: "threadPanelSubject",
      threadId: "c-8f21",
      panel: "landscape",
      subjectKind: "outcome",
      subjectId: "O-12",
      search: "",
    });
  });

  it("keeps the query string it was given", () => {
    expect(parseRoute("/t/c-8f21", "?q=deploys")).toEqual({
      name: "thread",
      threadId: "c-8f21",
      search: "?q=deploys",
    });
  });

  it("reads customize, its listing, and search", () => {
    expect(parseRoute("/customize")).toMatchObject({ name: "customize" });
    expect(parseRoute("/customize/l-1")).toMatchObject({
      name: "customizeListing",
      listingId: "l-1",
    });
    expect(parseRoute("/search")).toMatchObject({ name: "search" });
  });

  it("never throws: an unknown path is home", () => {
    expect(parseRoute("/nothing/here/at/all")).toEqual({ name: "home", search: "" });
  });
});

describe("routeToPath", () => {
  it("is the inverse of parseRoute for every route it can build", () => {
    const paths = [
      "/",
      "/t/c-8f21",
      "/t/c-8f21/landscape",
      "/t/c-8f21/landscape/outcome/O-12",
      "/customize",
      "/customize/l-1",
      "/search",
    ];
    for (const path of paths) {
      const route = parseRoute(path);
      expect(routeToPath(route)).toBe(path);
    }
  });

  it("formats the home route as a bare slash", () => {
    const route: Route = { name: "home" };
    expect(routeToPath(route)).toBe("/");
  });
});

describe("withSearch", () => {
  it("carries a query string onto the path", () => {
    expect(withSearch("/t/c-8f21", "?q=deploys")).toBe("/t/c-8f21?q=deploys");
  });

  it("leaves the path alone when there is no query", () => {
    expect(withSearch("/t/c-8f21", "")).toBe("/t/c-8f21");
  });
});
