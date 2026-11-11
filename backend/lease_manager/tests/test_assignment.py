"""Lease assignment: balanced, and nothing moves that does not have to.

Stdlib `unittest`, like the other services. `src.assignment` imports nothing,
so no env file is needed.

    cd backend/lease_manager && python -m unittest discover -s tests
"""

import itertools
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.assignment import moves, plan_leases  # noqa: E402


def shards(n):
    return [f"stream_shard:{i}" for i in range(n)]


def loads(plan):
    counts = {}
    for owner in plan.values():
        counts[owner] = counts.get(owner, 0) + 1
    return counts


class Balanced(unittest.TestCase):
    def assert_balanced(self, plan, consumers, n):
        self.assertEqual(sorted(plan), sorted(shards(n)), "every shard has an owner")
        self.assertTrue(set(plan.values()) <= set(consumers), "only live owners")
        counts = [loads(plan).get(c, 0) for c in consumers]
        self.assertLessEqual(max(counts) - min(counts), 1, counts)

    def test_from_nothing(self):
        for n, k in itertools.product([1, 2, 5, 16], [1, 2, 3, 7]):
            consumers = [f"c{i}" for i in range(k)]
            with self.subTest(shards=n, consumers=k):
                self.assert_balanced(plan_leases({}, consumers, shards(n)), consumers, n)

    def test_from_any_starting_point(self):
        """Random owners, some dead, plus stale shards: always ends balanced."""
        rng = random.Random(7)
        for _ in range(300):
            n, k = rng.randint(1, 16), rng.randint(1, 6)
            consumers = [f"c{i}" for i in range(k)]
            everyone = consumers + ["dead1", "dead2"]
            current = {s: rng.choice(everyone) for s in shards(n + rng.randint(0, 4))}
            with self.subTest(current=current, consumers=consumers):
                self.assert_balanced(plan_leases(current, consumers, shards(n)), consumers, n)

    def test_more_consumers_than_shards(self):
        plan = plan_leases({}, ["a", "b", "c"], shards(2))
        self.assertEqual(len(plan), 2)
        self.assertEqual(len(set(plan.values())), 2, "no consumer takes both")

    def test_no_consumers_assigns_nothing(self):
        self.assertEqual(plan_leases({"stream_shard:0": "dead"}, [], shards(2)), {})

    def test_order_of_the_consumer_set_does_not_matter(self):
        current = {"stream_shard:0": "dead"}
        self.assertEqual(
            plan_leases(current, ["a", "b", "c"], shards(5)),
            plan_leases(current, ["c", "a", "b"], shards(5)),
        )


class Sticky(unittest.TestCase):
    def test_a_balanced_plan_is_left_alone(self):
        plan = plan_leases({}, ["a", "b", "c"], shards(8))
        self.assertEqual(moves(plan, plan_leases(plan, ["a", "b", "c"], shards(8))), {})

    def test_a_dead_consumer_only_moves_its_own_shards(self):
        """What the 2026-11-11 run on a scaled stack got wrong."""
        before = {"stream_shard:0": "a", "stream_shard:1": "b"}
        after = plan_leases(before, ["b", "c"], shards(2))
        self.assertEqual(moves(before, after), {"stream_shard:0": "c"})

    def test_a_dead_consumer_with_many_shards(self):
        before = plan_leases({}, ["a", "b", "c"], shards(9))
        after = plan_leases(before, ["a", "b"], shards(9))
        moved = moves(before, after)
        self.assertEqual(set(moved), {s for s, o in before.items() if o == "c"})

    def test_a_new_consumer_takes_only_its_share(self):
        before = plan_leases({}, ["a", "b"], shards(6))
        after = plan_leases(before, ["a", "b", "c"], shards(6))
        moved = moves(before, after)
        self.assertEqual(len(moved), 2)
        self.assertEqual(set(moved.values()), {"c"})

    def test_raising_the_shard_count_keeps_existing_owners(self):
        before = plan_leases({}, ["a", "b"], shards(2))
        after = plan_leases(before, ["a", "b"], shards(4))
        for shard, owner in before.items():
            self.assertEqual(after[shard], owner)

    def test_stale_entries_outside_the_shard_list_are_ignored(self):
        """Dev's leases hash still names shards 2 to 15 from when it ran 16."""
        current = {f"stream_shard:{i}": "ghost" for i in range(16)}
        current["stream_shard:0"] = "a"
        plan = plan_leases(current, ["a", "b"], shards(2))
        self.assertEqual(plan, {"stream_shard:0": "a", "stream_shard:1": "b"})


if __name__ == "__main__":
    unittest.main()
