"""The real devin_run() against a fake `requests`: what is sent to Devin and how its answers are read."""
import importlib.util
import sys
import time
import types
import unittest
import uuid

from helpers import TEMPLATE

sys.path.insert(0, str(TEMPLATE / "pipeline"))


class Resp:
    def __init__(self, code=200, body=None):
        self.status_code, self._body = code, body or {}

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def load_run(posts, gets):
    sys.modules.setdefault("requests", types.ModuleType("requests"))
    spec = importlib.util.spec_from_file_location(f"run_{uuid.uuid4().hex}", TEMPLATE / "pipeline" / "run.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sent = []

    def post(url, headers=None, json=None):
        sent.append(dict(json))  # a copy: the code removes the field after the first request
        return posts.pop(0)

    mod.requests = types.SimpleNamespace(post=post, get=lambda url, headers=None: gets.pop(0))
    mod.time = types.SimpleNamespace(time=time.time, sleep=lambda s: None)
    mod.ORG = "org"
    return mod, sent


SESSION = {"session_id": "s1", "url": "https://app.devin.ai/sessions/x"}


def status(s, detail=None, acus=1.5):
    return Resp(200, {"status": s, "status_detail": detail, "acus_consumed": acus})


class DevinApiTests(unittest.TestCase):
    def test_the_acu_limit_is_sent_as_max_acu_limit(self):
        mod, sent = load_run([Resp(200, SESSION)], [status("exit")])
        mod.devin_run("do it", 5, acu_limit=3)
        self.assertEqual(sent, [{"prompt": "do it", "max_acu_limit": 3}])

    def test_no_limit_means_no_field(self):
        mod, sent = load_run([Resp(200, SESSION)], [status("exit")])
        mod.devin_run("do it", 5)
        self.assertEqual(sent, [{"prompt": "do it"}])

    def test_a_rejected_limit_is_retried_without_it_and_reported(self):
        mod, sent = load_run([Resp(422), Resp(200, SESSION)], [status("exit")])
        url, st, acus = mod.devin_run("do it", 5, acu_limit=3)
        self.assertEqual([("max_acu_limit" in s) for s in sent], [True, False])
        self.assertEqual((st, acus), ("exit", 1.5))
        self.assertTrue(any("without a hard ACU cap" in w for w in mod.DEVIN_WARNINGS))

    def test_other_errors_are_not_swallowed(self):
        mod, _ = load_run([Resp(500)], [])
        with self.assertRaises(RuntimeError):
            mod.devin_run("do it", 5, acu_limit=3)

    def test_the_documented_limit_status_is_returned_as_acu_limit(self):
        mod, _ = load_run([Resp(200, SESSION)], [status("running", "total_session_limit_exceeded", acus=3)])
        self.assertEqual(mod.devin_run("do it", 5, acu_limit=3)[1:], ("acu_limit", 3))

    def test_idle_for_two_polls_still_means_finished(self):
        mod, _ = load_run([Resp(200, SESSION)], [status("running", "waiting_for_user"), status("running", "waiting_for_user")])
        self.assertEqual(mod.devin_run("do it", 5)[1], "waiting_for_user")


if __name__ == "__main__":
    unittest.main()
