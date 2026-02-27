import json
import os
import time
import urllib.request
import urllib.error


def _hit(url: str, timeout: int = 180) -> dict:
    started = time.time()
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            elapsed_ms = int((time.time() - started) * 1000)
            return {
                "url": url,
                "ok": 200 <= resp.status < 300,
                "status": resp.status,
                "elapsed_ms": elapsed_ms,
                "content_type": resp.headers.get("content-type", ""),
                "body_prefix": body[:120],
            }
    except urllib.error.HTTPError as exc:
        elapsed_ms = int((time.time() - started) * 1000)
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return {
            "url": url,
            "ok": False,
            "status": exc.code,
            "elapsed_ms": elapsed_ms,
            "error": str(exc),
            "body_prefix": body[:120],
        }
    except Exception as exc:
        elapsed_ms = int((time.time() - started) * 1000)
        return {
            "url": url,
            "ok": False,
            "status": None,
            "elapsed_ms": elapsed_ms,
            "error": str(exc),
        }


def handler(event, context):
    url_en = os.environ["PREWARM_URL_EN"]
    url_zh = os.environ["PREWARM_URL_ZH"]
    results = [_hit(url_en), _hit(url_zh)]
    success = all(r.get("ok") for r in results)

    output = {
        "success": success,
        "results": results,
    }
    print(json.dumps(output, ensure_ascii=False))

    if not success:
        raise RuntimeError(json.dumps(output))

    return output
