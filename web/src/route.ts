import { useEffect, useState } from "react";

// Pages live after the # (/#/board, /#/add), so the server only ever serves one
// page and the back button still works.
export type Route = { page: "board"; card: number | null } | { page: "add" };

function parse(hash: string): Route {
  const [path, query] = hash.replace(/^#/, "").split("?");
  if (path === "/add") return { page: "add" };
  const card = Number(new URLSearchParams(query).get("card"));
  return { page: "board", card: Number.isInteger(card) && card > 0 ? card : null };
}

export function go(route: Route) {
  window.location.hash = route.page === "add" ? "/add" : route.card ? `/board?card=${route.card}` : "/board";
}

export function useRoute(): Route {
  const [route, setRoute] = useState(() => parse(window.location.hash));
  useEffect(() => {
    const onChange = () => setRoute(parse(window.location.hash));
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return route;
}
