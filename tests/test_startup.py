import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from scripts.serve import check_existing_api, main


class StartupTests(unittest.TestCase):
    def server(self, status=None, title='COVID Research Search API'):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                payload = {'info': {'title': title, 'version': '1.0.0'}} if self.path == '/openapi.json' else status
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(payload).encode())

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server.server_port

    def status(self, **changes):
        return dict(ready=True, dataset='BEIR TREC-COVID / CORD-19',
                    assignmentReady=True, maxDocs=20000, **changes)

    def test_existing_matching_api_is_reused(self):
        port = self.server(self.status())
        self.assertTrue(check_existing_api('127.0.0.1', port, False, 20000))

    def test_unrelated_service_is_rejected(self):
        port = self.server(self.status(), title='Another API')
        with self.assertRaisesRegex(RuntimeError, 'another service'):
            check_existing_api('127.0.0.1', port, False, 20000)

    def test_existing_demo_cannot_replace_transformer(self):
        status = self.status()
        status['assignmentReady'] = False
        port = self.server(status)
        with self.assertRaisesRegex(RuntimeError, 'different mode or corpus scope'):
            check_existing_api('127.0.0.1', port, False, 20000)

    def test_different_corpus_scope_is_rejected(self):
        port = self.server(self.status())
        with self.assertRaisesRegex(RuntimeError, 'different mode or corpus scope'):
            check_existing_api('127.0.0.1', port, False, 0)

    def test_matching_api_is_checked_before_model_dependencies(self):
        with patch('scripts.serve.check_existing_api', return_value=True), \
                patch('scripts.serve.importlib.util.find_spec') as find_spec:
            self.assertEqual(main([]), 0)
            find_spec.assert_not_called()


if __name__ == '__main__':
    unittest.main()
