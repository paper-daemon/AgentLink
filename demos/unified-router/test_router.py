"""Tests for the Unified Router demo."""

import unittest

import router as rmod


class RouterTest(unittest.TestCase):
    def setUp(self):
        self.router = rmod.build_demo_router()

    def test_unknown_operation_rejected(self):
        with self.assertRaises(KeyError):
            self.router.call("fly_to_moon")

    def test_first_call_is_cold_second_is_warm(self):
        first = self.router.call("read_file", {"path": "/x"})
        second = self.router.call("read_file", {"path": "/x"})
        self.assertEqual(first["connection"], "cold")
        self.assertEqual(second["connection"], "warm")
        self.assertGreater(first["total_ms"], second["total_ms"])
        self.assertEqual(first["checksum"], second["checksum"])

    def test_segments_are_reported_separately(self):
        out = self.router.call("list_directory", {"path": "/"})
        self.assertEqual(set(out["segments"]),
                         {"connect_ms", "transport_ms", "node_exec_ms"})
        self.assertEqual(out["total_ms"], sum(out["segments"].values()))

    def test_failover_moves_agnostic_ops_with_identical_payload(self):
        before = self.router.call("read_file", {"path": "/docs/a.txt"})
        self.router.nodes["node-a"].up = False
        # probe cache from the first call is still fresh; force a re-probe
        self.router.probe_all(force=True)
        after = self.router.call("read_file", {"path": "/docs/a.txt"})
        self.assertTrue(after["failover"])
        self.assertEqual(after["served_by"], "node-b")
        # payload differs only in routing bookkeeping, so compare checksums:
        self.assertEqual(before["checksum"], after["checksum"])

    def test_stale_health_cache_self_heals_via_failed_call(self):
        self.router.call("read_file", {"path": "/x"})  # caches "a is up"
        self.router.nodes["node-a"].up = False         # ...then a dies
        out = self.router.call("read_file", {"path": "/x"})  # no force
        self.assertEqual(out["served_by"], "node-b")
        self.assertTrue(out["failover"])

    def test_bound_op_refuses_to_move(self):
        self.router.nodes["node-a"].up = False
        self.router.probe_all(force=True)
        with self.assertRaises(rmod.NodeDownError):
            self.router.call("run_terminal", {"cmd": "ls"})

    def test_all_candidates_down_is_a_clean_error(self):
        self.router.nodes["node-a"].up = False
        self.router.nodes["node-b"].up = False
        self.router.probe_all(force=True)
        with self.assertRaises(rmod.NodeDownError):
            self.router.call("read_file", {"path": "/x"})

    def test_probe_cache_holds_within_ttl(self):
        self.assertTrue(self.router.probe("node-a", force=True))
        self.router.nodes["node-a"].up = False
        # cached value is served until the TTL expires or a probe is forced
        self.assertTrue(self.router.probe("node-a"))
        self.assertFalse(self.router.probe("node-a", force=True))


if __name__ == "__main__":
    unittest.main()
