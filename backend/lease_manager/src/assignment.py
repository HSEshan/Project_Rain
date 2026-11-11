"""Which consumer reads which stream shard. Pure: no Redis, no config.

The rule is **balanced, and sticky**. Balanced: every live consumer holds either
`floor(shards / consumers)` shards or one more. Sticky: a shard stays with the
consumer that holds it unless that consumer is gone or holds more than its share.

Sticky matters because moving a shard is not free. The old owner's worker is
cancelled when it notices, possibly between reading a batch and acknowledging it,
which leaves those entries in the group's pending list for a reclaim to find; and
for a moment both consumers may read the shard, which is the one place per-shard
ordering can slip. The first version recomputed from scratch every five seconds
in whatever order the consumer set came back, so one consumer dying moved shards
whose owners were perfectly healthy (seen 2026-11-11 with three consumers).
"""


def plan_leases(
    current: dict[str, str], consumers: list[str], shards: list[str]
) -> dict[str, str]:
    """The assignment for `shards` over live `consumers`, moving as few as possible.

    `current` may name dead consumers and shards outside `shards`; both are
    ignored. Returns an entry for every shard, or nothing when no consumer is
    alive (an owner that is gone is better left in place than replaced by
    nobody, since nothing would read the shard either way).
    """
    if not consumers:
        return {}

    live = sorted(set(consumers))
    base, extra = divmod(len(shards), len(live))
    held: dict[str, list[str]] = {consumer: [] for consumer in live}

    # Keep every shard whose owner is alive, up to the larger share for now.
    unassigned: list[str] = []
    for shard in shards:
        owner = current.get(shard)
        if owner in held and len(held[owner]) < base + 1:
            held[owner].append(shard)
        else:
            unassigned.append(shard)

    # Only `extra` consumers may keep the larger share. Those already holding it
    # keep it in a stable order; anyone else over `base` gives the excess back.
    over = [consumer for consumer in live if len(held[consumer]) > base]
    for consumer in over[extra:]:
        unassigned.extend(held[consumer][base:])
        del held[consumer][base:]
    larger_left = extra - min(len(over), extra)

    # Hand out what is left to whoever holds least, ties by id, so the outcome
    # does not depend on the order Redis returned the consumer set in.
    for shard in sorted(unassigned, key=shards.index):
        candidates = [
            consumer
            for consumer in live
            if len(held[consumer]) < base
            or (len(held[consumer]) == base and larger_left > 0)
        ]
        consumer = min(candidates, key=lambda c: (len(held[c]), c))
        if len(held[consumer]) == base:
            larger_left -= 1
        held[consumer].append(shard)

    return {shard: consumer for consumer, owned in held.items() for shard in owned}


def moves(before: dict[str, str], after: dict[str, str]) -> dict[str, str]:
    """The entries of `after` that differ from `before`, which is all to write."""
    return {shard: owner for shard, owner in after.items() if before.get(shard) != owner}
