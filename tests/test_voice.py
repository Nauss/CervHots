import threading
import unittest
from types import SimpleNamespace

from cerveau.voice import send_to_mumble


class VoiceTests(unittest.TestCase):
    def bot(self, quiet=True, lost=False):
        sent = []
        event = threading.Event()
        event.set()
        def add_sound(pcm):
            sent.append(pcm)
            return event
        return SimpleNamespace(
            wait_for_quiet=lambda **kwargs: quiet, _lost=lost,
            mumble=SimpleNamespace(users=SimpleNamespace(myself=object()),
                                   send_audio=SimpleNamespace(add_sound=add_sound),
                                   is_alive=lambda: True),
        ), sent

    def test_prepared_pcm_reaches_mumble_without_resynthesis(self):
        bot, sent = self.bot()
        speech = SimpleNamespace(pcm=b"\0\0" * 10, duration_s=0.01)
        self.assertTrue(send_to_mumble(bot, speech, lambda: True))
        self.assertEqual(sent, [speech.pcm])

    def test_people_speaking_or_expired_advice_never_enqueue_audio(self):
        for quiet, fresh in ((False, True), (True, False)):
            bot, sent = self.bot(quiet)
            self.assertFalse(send_to_mumble(bot, None, lambda fresh=fresh: fresh))
            self.assertEqual(sent, [])

    def test_disconnected_bot_fails_without_enqueueing(self):
        bot, sent = self.bot(lost=True)
        with self.assertRaises(RuntimeError):
            send_to_mumble(bot, None, lambda: True)
        self.assertEqual(sent, [])


if __name__ == "__main__":
    unittest.main()
