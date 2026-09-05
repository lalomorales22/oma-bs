"""Real FFprobe must not follow network references disguised as gallery media."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shutil
import tempfile
import threading
import unittest
from test_backend import load_backend


@unittest.skipUnless(shutil.which('ffprobe'), 'FFprobe required')
class MediaSecurityTests(unittest.TestCase):
    def test_disguised_playlist_cannot_fetch_network(self):
        requests = []
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                requests.append(self.path)
                self.send_response(404)
                self.end_headers()
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as temp:
                home = Path(temp)
                backend = load_backend(home)
                source = home / 'Videos/OMA-BS/untrusted.mp4'
                source.parent.mkdir(parents=True)
                source.write_text('#EXTM3U\n#EXT-X-TARGETDURATION:1\n#EXTINF:1,\n'
                                  f'http://127.0.0.1:{server.server_port}/segment.ts\n#EXT-X-ENDLIST\n')
                with self.assertRaises(RuntimeError):
                    backend.inspect_media(str(source), thumbnail=False)
                self.assertEqual(requests, [])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
