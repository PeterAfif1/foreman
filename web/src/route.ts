import { useEffect, useState } from "react";

// Pages live after the # (/#/board, /#/add), so the server only ever serves one
// page and the back button still works.
export type Route = { page: "board"; card: number | null } | { page: "add" } | { page: "usage" };

function parse(hash: string): Route {
  const [path, query] = hash.replace(/^#/, "").split("?");
  if (path === "/add") return { page: "add" };
  if (path === "/usage") return { page: "usage" };
  const card = Number(new URLSearchParams(query).get("card"));
  return { page: "board", card: Number.isInteger(card) && card > 0 ? card : null };
}

export function go(route: Route) {
  if (route.page !== "board") window.location.hash = `/${route.page}`;
  else window.location.hash = route.card ? `/board?card=${route.card}` : "/board";
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
