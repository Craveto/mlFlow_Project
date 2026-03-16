from pathlib import Path
import os
import sys


def main():
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))
    sys.path.insert(0, str(repo_root / "dashboard"))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "timeseries_dashboard.settings")

    import django

    django.setup()

    from django.urls import resolve

    expected_routes = {
        "/api/overview/": "api_overview",
        "/api/forecast/": "api_forecast",
        "/api/drift/": "api_drift",
        "/api/roi/": "api_roi",
    }

    for route, view_name in expected_routes.items():
        resolved = resolve(route)
        if resolved.view_name != view_name:
            raise SystemExit(f"Route {route} resolved to {resolved.view_name}, expected {view_name}")

    frontend_files = [
        repo_root / "frontend" / "index.html",
        repo_root / "frontend" / "drift.html",
        repo_root / "frontend" / "roi.html",
        repo_root / "frontend" / "assets" / "api.js",
        repo_root / "frontend" / "assets" / "app.css",
    ]
    missing = [str(path) for path in frontend_files if not path.exists()]
    if missing:
        raise SystemExit(f"Missing frontend files: {missing}")

    print("CI smoke check passed.")


if __name__ == "__main__":
    main()
