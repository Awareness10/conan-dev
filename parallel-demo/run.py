"""Parallel uploads and downloads against a local server, to watch the progress hook.

    uv run parallel-demo/run.py                 # 1 x 3500 MiB + 7 x 400 MiB packages
    uv run parallel-demo/run.py --big-mib 1000 --mib 100   # quicker
    uv run parallel-demo/run.py --keep          # keep the ~20 GB work folder

What it does, in ~/.cache/conan-parallel-demo (an isolated CONAN_HOME, your own is
not touched):

1. starts conan_server (in a throwaway `uv run --with conan-server` environment:
   it bundles its own `conan` package) behind a proxy that limits every
   connection to --rate MB/s, so transfers take long enough to watch
2. installs the conan_config working copy (--config, default ../conan_config),
   so core.upload:parallel / core.download:parallel come from its global.conf
3. creates --count packages blob0..blobN of random bytes (blob0 is --big-mib)
4. `conan upload`: compression + upload bars, in parallel
5. removes them from the cache, then `conan install`: download + unpack bars

Steps 4 and 5 run in your terminal, so you see the live output. Try
CONAN_PROGRESS_THEME=btop, a small terminal, or `| cat` for CI-style output.
"""

import argparse
import http.client
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def serve(server_dir, port, public_port):
    """conan_server's app on a multi-threaded WSGI server (the stock one serves one
    request at a time, which would make the parallel transfers take turns)."""
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

        def forward(self):
            size = int(self.headers.get("Content-Length") or 0)
            body = Throttled(self.rfile, size) if size else None
            headers = {k: v for k, v in self.headers.items() if k.lower() != "host"}
            headers["Host"] = f"localhost:{port}"
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


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--count", type=int, default=8, help="packages (default 8)")
    parser.add_argument("--big-mib", type=int, default=3500, help="blob0 size")
    parser.add_argument("--mib", type=int, default=400, help="size of the others")
    parser.add_argument("--rate", type=float, default=100, help="MB/s per connection")
    parser.add_argument(
        "--port", type=int, default=9300, help="server port (+1: proxy)"
    )
    parser.add_argument("--config", default=str(HERE.parents[1] / "conan_config"))
    parser.add_argument(
        "--work", default=str(Path.home() / ".cache" / "conan-parallel-demo")
    )
    parser.add_argument("--keep", action="store_true", help="keep the work folder")
    args = parser.parse_args()

    work, port = Path(args.work), args.port
    home = work / "home"
    work.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "CONAN_HOME": str(home), "CONAN_CONFIG_SYNC_SKIP": "1"}
    bindir = Path(sys.executable).parent
    conan = str(bindir / "conan") if (bindir / "conan").exists() else "conan"
    names = [f"blob{i}" for i in range(args.count)]

    def run(*cmd, show=False):
        if show:
            print(f"\n$ conan {' '.join(cmd)}", flush=True)
        out = None if show else subprocess.DEVNULL
        subprocess.run([conan, *cmd], env=env, check=True, stdout=out, stderr=out)

    here = [sys.executable, __file__]
    server = subprocess.Popen(
        ["uv", "run", "--quiet", "--no-project", "--with", "conan-server", "python"]
        + [__file__, "--serve", str(work / "server"), str(port), str(port + 1)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    rate = str(int(args.rate * 1e6))
    throttle = subprocess.Popen(here + ["--proxy", str(port + 1), str(port), rate])
    try:
        print(
            f"Starting conan_server on :{port}, {args.rate:g} MB/s proxy on :{port + 1}"
        )
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

        print(f"Installing {args.config} into {home}")
        run("config", "install", args.config)
        run("remote", "add", "local", f"http://localhost:{port + 1}", "--force")
        run("remote", "login", "local", "demo", "-p", "demo")
        subprocess.run(
            [conan, "config", "show", "core.*:parallel"], env=env, check=False
        )
        run("remove", "blob*", "-c")
        run("remove", "blob*", "-r", "local", "-c")

        for i, name in enumerate(names):
            mib = args.big_mib if i == 0 else args.mib
            print(f"Creating {name}/0.1 ({mib} MiB)", flush=True)
            env["PARALLEL_DEMO_MIB"] = str(mib)
            run("create", str(HERE), "--name", name)

        run("upload", "blob*", "-r", "local", "-c", show=True)
        run("remove", "blob*", "-c")
        requires = [f"--requires={name}/0.1" for name in names]
        run(
            "install", *requires, "-r", "local", "-of", str(work / "install"), show=True
        )
    finally:
        throttle.terminate()
        server.terminate()
        if not args.keep:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    if sys.argv[1:2] == ["--serve"]:
        serve(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))
    elif sys.argv[1:2] == ["--proxy"]:
        proxy(int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]))
    else:
        main()
