"""Inspect real RTMP wire bytes: a permissive listener alone missed empty keys."""
import importlib.util
import json
import os
from pathlib import Path
import socket
import ssl
import subprocess
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('transport', ROOT / 'studio/stream_transport.py')
transport = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transport)


class TransportTests(unittest.TestCase):
    def test_rtmps_rejects_untrusted_certificate_before_sending_key(self):
        with tempfile.TemporaryDirectory() as directory, socket.socket() as listener:
            folder = Path(directory)
            cert, private = folder / 'cert.pem', folder / 'key.pem'
            subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
                '-subj', '/CN=localhost', '-keyout', str(private), '-out', str(cert)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=10)
            listener.bind(('127.0.0.1', 0)); listener.listen(1); listener.settimeout(10)
            received = []
            def server():
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                context.load_cert_chain(cert, private)
                try:
                    with listener.accept()[0] as connection:
                        connection.settimeout(5)
                        with context.wrap_socket(connection, server_side=True) as secured:
                            received.append(secured.recv(1537))
                except (OSError, ssl.SSLError):
                    pass
            thread = threading.Thread(target=server, daemon=True); thread.start()
            destination = folder / 'connection.json'
            key = 'synthetic_private_key_never_send'
            destination.write_text(json.dumps({'url':f'rtmps://127.0.0.1:{listener.getsockname()[1]}/app', 'key':key}))
            destination.chmod(0o600)
            result = subprocess.run([os.environ.get('OMA_BS_TRANSPORT_PYTHON', '/usr/bin/python3'),
                str(ROOT / 'studio/stream_transport.py'), str(destination), 'ready'],
                input=b'', capture_output=True, timeout=15)
            thread.join(timeout=6)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b'Certificate verify failed', result.stderr)
            self.assertNotIn(key.encode(), result.stderr + result.stdout)
            self.assertFalse(any(received))

    def test_rejects_public_or_symlink_credentials_and_redacts_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'connection.json'
            path.write_text(json.dumps({'url': 'rtmp://example.test/app', 'key': 'synthetic-key'}))
            path.chmod(0o644)
            with self.assertRaises(ValueError):
                transport.read_destination(path)
            path.chmod(0o600)
            link = Path(directory) / 'link'
            link.symlink_to(path)
            with self.assertRaises(OSError):
                transport.read_destination(link)
        self.assertEqual(transport.safe_error(RuntimeError('Authentication failed: synthetic-key')), 'Authentication failed')

    def test_rtmp_wire_has_application_and_private_publish_name(self):
        with tempfile.TemporaryDirectory() as directory, socket.socket() as proxy:
            folder = Path(directory)
            with socket.socket() as port_socket:
                port_socket.bind(('127.0.0.1', 0))
                receiver_port = port_socket.getsockname()[1]
            proxy.bind(('127.0.0.1', 0))
            proxy.listen(1)
            proxy.settimeout(10)
            proxy_port = proxy.getsockname()[1]
            key = 'synthetic_private_publish_name_123'
            destination = folder / 'connection.json'
            destination.write_text(json.dumps({'url': f'rtmp://127.0.0.1:{proxy_port}/app', 'key': key}))
            destination.chmod(0o600)
            output = folder / 'received.flv'
            receiver = subprocess.Popen(['ffmpeg', '-nostdin', '-v', 'error', '-listen', '1', '-i',
                f'rtmp://127.0.0.1:{receiver_port}/app/expected', '-c', 'copy', '-f', 'flv', str(output)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            captured, errors = bytearray(), []
            def bridge():
                try:
                    with proxy.accept()[0] as client, socket.create_connection(('127.0.0.1', receiver_port), timeout=10) as upstream:
                        client.settimeout(10)
                        def copy(source, target, record=False):
                            try:
                                while True:
                                    data = source.recv(65536)
                                    if not data:
                                        break
                                    if record and len(captured) < 262144:
                                        captured.extend(data[:262144-len(captured)])
                                    target.sendall(data)
                            except OSError:
                                pass
                            finally:
                                try: target.shutdown(socket.SHUT_WR)
                                except OSError: pass
                        reader = threading.Thread(target=copy, args=(upstream, client), daemon=True)
                        reader.start()
                        copy(client, upstream, True)
                        reader.join(timeout=11)
                except Exception as error:
                    errors.append(type(error).__name__)
            thread = threading.Thread(target=bridge, daemon=True)
            try:
                time.sleep(.3)
                thread.start()
                media = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-f', 'lavfi', '-i',
                    'color=c=black:size=160x90:rate=30', '-t', '2', '-c:v', 'libx264', '-threads', '1',
                    '-preset', 'ultrafast', '-tune', 'zerolatency', '-f', 'mpegts', 'pipe:1'],
                    capture_output=True, check=True, timeout=10).stdout
                command = [os.environ.get('OMA_BS_TRANSPORT_PYTHON', '/usr/bin/python3'),
                           str(ROOT / 'studio/stream_transport.py'), str(destination), 'none']
                self.assertNotIn(key, repr(command))
                worker = subprocess.run(command, input=media, capture_output=True, timeout=15)
                self.assertEqual(worker.returncode, 0, worker.stderr.decode())
                self.assertNotIn(key.encode(), worker.stdout + worker.stderr)
                thread.join(timeout=11)
                self.assertFalse(errors, errors)
                # AMF property 'app', string value 'app', and actual publish key.
                self.assertIn(b'\x00\x03app\x02\x00\x03app', captured)
                self.assertIn(b'publish', captured)
                self.assertIn(key.encode(), captured)
                receiver.wait(timeout=5)
                data = subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', str(output)])
                codecs = {row['codec_name'] for row in json.loads(data)['streams']}
                self.assertEqual(codecs, {'h264', 'aac'})
            finally:
                if receiver.poll() is None:
                    receiver.kill()
                receiver.wait()


if __name__ == '__main__':
    unittest.main()
