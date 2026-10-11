"""Decode public item payloads and require an exact product match."""
from __future__ import annotations

import json
import re
from .errors import CollectionError


def decode_nuxt(page):
    match = re.search(r'<script\b[^>]*\bid=[\"\']__NUXT_DATA__[\"\'][^>]*>(.*?)</script>', page, re.S | re.I)
    if not match:
        raise CollectionError("No public Nuxt payload found; page layout may have changed")
    flat = json.loads(match.group(1))
    if not isinstance(flat, list):
        raise CollectionError("Unexpected Nuxt payload shape")
    memo = {}

    def resolve(index):
        if not isinstance(index, int):
            raise CollectionError("Invalid Nuxt reference")
        if index < 0:
            return None  # devalue undefined / non-finite / empty special values
        if index in memo:
            return memo[index]
        if index >= len(flat):
            raise CollectionError("Nuxt reference out of range")
        node = flat[index]
        if isinstance(node, dict):
            result = {}
            memo[index] = result
            result.update({key: resolve(ref) for key, ref in node.items()})
        elif isinstance(node, list):
            if node and isinstance(node[0], str):
                kind = node[0]
                if kind in {"ShallowReactive", "Reactive", "Ref", "ShallowRef"}:
                    if len(node) != 2:
                        raise CollectionError(f"Unexpected Nuxt {kind} wrapper")
                    result = resolve(node[1])
                elif kind == "EmptyRef":
                    result = None
                elif kind == "Set":
                    result = [resolve(ref) for ref in node[1:]]
                else:
                    raise CollectionError(f"Unsupported Nuxt wrapper: {kind}")
                memo[index] = result
            else:
                result = []
                memo[index] = result
                result.extend(resolve(ref) for ref in node)
        else:
            result = node
            memo[index] = result
        return result

    return resolve(0)


def parse_public(page, expected_name):
    root = decode_nuxt(page)
    responses = root.get("data", {})
    item = None
    related = None
    for response in responses.values():
        if not isinstance(response, dict) or response.get("success") is not True:
            continue
        data = response.get("data")
        if not isinstance(data, dict):
            continue
        if data.get("marketHashName") == expected_name and "sellingPriceList" in data:
            item = data
        if "relatedList" in data and "all" in data:
            related = data
    if item is None:
        raise CollectionError(f"No matching live item payload for {expected_name}")
    if not isinstance(item.get("sellingPriceList"), list):
        raise CollectionError("Unexpected public quote list")
    related_rows = related.get("all", []) if related else []
    if not isinstance(related_rows, list):
        raise CollectionError("Unexpected related variants")
    exact = next((row for row in related_rows if row.get("marketHashName") == expected_name), {})
    return item, related_rows, exact
