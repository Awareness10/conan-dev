"""The demo remote and an isolated Conan home, shared by the demos' run.py scripts.

The remote is a local conan_server (run in a throwaway `uv run --with conan-server`
environment: it bundles its own `conan` package) behind a proxy that limits every
connection to a rate, so transfers take long enough to watch. Standard library
only: the demos may run on another Python (parallel-demo/run-3.12.7.py).
"""

import contextlib
import http.client
import io
import os
import platform
import socket
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REMOTE = "demo"  # remote name in the demo's Conan home; user demo, password demo


def add_arguments(parser, work, rate):
    """The options every demo takes (work: default work folder name in ~/.cache)."""
    parser.add_argument(
        "--rate", type=float, default=rate, help=f"MB/s per connection ({rate:g})"
    )
    parser.add_argument(
        "--port", type=int, default=9300, help="server port (+1: proxy)"
    )
    parser.add_argument("--config", default=str(HERE.parent / "conan_config"))
    parser.add_argument("--work", default=str(Path.home() / ".cache" / work))
    parser.add_argument("--keep", action="store_true", help="keep the work folder")


class Conan:
    """`conan` in an isolated CONAN_HOME (work/home): yours is not touched."""

    def __init__(self, work):
        self.home = Path(work) / "home"
        self.env = {
            **os.environ,
            "CONAN_HOME": str(self.home),
            "CONAN_CONFIG_SYNC_SKIP": "1",
        }
        bindir = Path(sys.executable).parent
        self.exe = str(bindir / "conan") if (bindir / "conan").exists() else "conan"

    def __call__(self, *cmd, show=False, check=True):
        """Run conan; show=True prints the command and lets its output through."""
        if show:
            print(f"\n$ conan {' '.join(cmd)}", flush=True)
        out = None if show else subprocess.DEVNULL
        return subprocess.run(
            [self.exe, *cmd], env=self.env, check=check, stdout=out, stderr=out
        )

    def output(self, *cmd):
        """Run conan quietly; returns its stdout, stripped."""
        result = subprocess.run(
            [self.exe, *cmd], env=self.env, capture_output=True, text=True, check=True
        )
        return result.stdout.strip()

    def version(self):
        result = subprocess.run(
            [self.exe, "--version"], capture_output=True, text=True, check=False
        )
        python = f"Python {platform.python_version()} ({sys.executable})"
        return f"{result.stdout.strip()} on {python}"

    def setup(self, config, url):
        """Install the conan_config working copy and add the demo remote."""
        print(f"Installing {config} into {self.home}", flush=True)
        self("config", "install", config)
        self("remote", "add", REMOTE, url, "--force")
        self("remote", "login", REMOTE, "demo", "-p", "demo")


@contextlib.contextmanager
def demo_remote(work, port, rate):
    """Start the server (port) and the proxy (port + 1); yields the remote URL."""
    for p in (port, port + 1):  # don't talk to another demo's server by accident
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", p)) == 0:
                sys.exit(f"Port {p} is in use (another demo running?): try --port")
    server = subprocess.Popen(
        ["uv", "run", "--quiet", "--no-project", "--with", "conan-server", "python"]
        + [__file__, "--serve", str(Path(work, "server")), str(port), str(port + 1)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    throttle = subprocess.Popen(
        [sys.executable, __file__, "--proxy", str(port + 1), str(port)]
        + [str(int(rate * 1e6))]
    )
    try:
        print(f"Starting conan_server on :{port}, {rate:g} MB/s proxy on :{port + 1}")
        for _ in range(240):  # the first run downloads conan-server
            try:
                conn = http.client.HTTPConnection("127.0.0.1", port + 1, timeout=2)
                conn.request("GET", "/v1/ping")
                if conn.getresponse().status == 200:
                    break
            except OSError:
                pass
            if server.poll() is not None:
                sys.exit("conan_server didn't start (is uv installed?)")
            time.sleep(0.5)
        else:
            sys.exit("conan_server didn't answer")
        yield f"http://localhost:{port + 1}"
    finally:
        throttle.terminate()
        server.terminate()


def serve(server_dir, port, public_port):
    """conan_server's app on a multi-threaded WSGI server (the stock one serves one
    request at a time, which would make parallel transfers take turns)."""
    from socketserver import ThreadingMixIn
    from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

    from conans.server.launcher import ServerLauncher

    ServerLauncher(server_dir=server_dir)  # writes the default server.conf
    conf = Path(server_dir, "server.conf")
    lines = []
    for line in conf.read_text().splitlines():
        if line.startswith("port:"):
            line = f"port: {port}"
        elif line.startswith("public_port:"):
            line = f"public_port: {public_port}"  # file URLs go through the proxy
        lines.append(line)
        if line.strip() == "[write_permissions]":
            lines.append("*/*@*/*: *")
    conf.write_text("\n".join(lines) + "\n")
    app = ServerLauncher(server_dir=server_dir).server.root_app

    class Server(ThreadingMixIn, WSGIServer):
        daemon_threads = True

    class Quiet(WSGIRequestHandler):
        def log_message(self, *args):
            pass

    make_server("127.0.0.1", port, app, Server, Quiet).serve_forever()


def proxy(port, backend, rate):
    """Reverse proxy port -> backend, each request/response body at `rate` bytes/s."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Throttled:
        def __init__(self, f, size):
            self.f, self.left, self.sent, self.start = f, size, 0, time.monotonic()

        def read(self, size=-1):
            size = self.left if size < 0 else min(size, self.left)
            data = self.f.read(size)
            self.left -= len(data)
            self.sent += len(data)
            ahead = self.sent / rate - (time.monotonic() - self.start)
            if ahead > 0:
                time.sleep(ahead)
            return data

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):
            pass

        def read_chunked(self):
            """The whole Transfer-Encoding: chunked request body."""
            data = b""
            while size := int(self.rfile.readline().split(b";")[0], 16):
                data += self.rfile.read(size)
                self.rfile.readline()  # the CRLF after each chunk
            while self.rfile.readline() not in (b"\r\n", b"\n", b""):
                pass  # trailer
            return data

        def forward(self):
            skip = {"host", "transfer-encoding", "content-length"}
            headers = {k: v for k, v in self.headers.items() if k.lower() not in skip}
            headers["Host"] = f"localhost:{port}"
            # requests sends an empty file chunked (it can't tell its length), e.g.
            # a header-only package's conaninfo.txt: forward it with a length
            if "chunked" in self.headers.get("Transfer-Encoding", "").lower():
                data = self.read_chunked()
                size = len(data)
                body = Throttled(io.BytesIO(data), size) if size else None
            else:
                size = int(self.headers.get("Content-Length") or 0)
                body = Throttled(self.rfile, size) if size else None
            if size or self.command in ("PUT", "POST"):
                headers["Content-Length"] = str(size)
            conn = http.client.HTTPConnection("127.0.0.1", backend, timeout=600)
            try:
                conn.request(self.command, self.path, body=body, headers=headers)
                response = conn.getresponse()
            except ConnectionRefusedError:  # the server is still starting
                self.send_error(502)
                return
            self.send_response(response.status)
            for k, v in response.getheaders():
                if k.lower() not in ("transfer-encoding", "connection"):
                    self.send_header(k, v)
            if response.getheader("Content-Length") is None:
                data = response.read()
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            else:
                self.end_headers()
                out = Throttled(response, int(response.getheader("Content-Length")))
                while chunk := out.read(256 * 1024):
                    self.wfile.write(chunk)
            conn.close()

        do_GET = do_PUT = do_POST = do_DELETE = do_HEAD = forward

    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    if sys.argv[1:2] == ["--serve"]:
        serve(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))
    elif sys.argv[1:2] == ["--proxy"]:
        proxy(int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]))
