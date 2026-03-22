import random


def prepare_pairs(
    lines,
    normalize_url,
    strip_tracking,
    mode="sequential",
    strip_utm=False,
    start=1,
    end=0,
    max_tabs=0,
    user_input=None,
    specific_urls=None,
):
    raw_links = [l.strip() for l in lines if l.strip() and not l.strip().startswith("#")]

    if specific_urls:
        raw_links = list(specific_urls)

    if user_input:
        raw_links = [l.replace("{input}", user_input) for l in raw_links]

    orig_links = [normalize_url(l) for l in raw_links if normalize_url(l)]
    links = [strip_tracking(u) for u in orig_links] if strip_utm else orig_links
    pairs = list(zip(orig_links, links))

    if mode == "reverse":
        pairs.reverse()
    elif mode == "shuffle":
        random.shuffle(pairs)

    start_idx = max(0, int(start) - 1)
    end_idx = int(end) if int(end) > 0 else len(pairs)
    pairs = pairs[start_idx:end_idx]

    if int(max_tabs) > 0:
        pairs = pairs[: int(max_tabs)]

    return pairs
