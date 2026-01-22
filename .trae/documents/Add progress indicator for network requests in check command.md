I will implement a progress indicator for the `check` command to improve user experience during network requests.

Plan:

1. **Modify** **`src/uv_lens/resolver.py`**:

   * Update `resolve_latest_versions` to accept optional `on_fetch_start` and `on_fetch_complete` callbacks.

   * Invoke `on_fetch_start` with the number of items to fetch before starting the requests.

   * Invoke `on_fetch_complete` inside the worker loop after each request completes.

2. **Modify** **`src/uv_lens/app.py`**:

   * Update `check_pyproject` to accept the same callbacks and pass them to `resolve_latest_versions`.

   * Update `run_check` to integrate `rich.progress`.

     * Create callbacks that initialize and update a `rich` progress bar (outputting to stderr).

     * Pass these callbacks to `check_pyproject`.

     * Ensure the progress bar is transient (disappears after completion) and only activates if there are items to fetch.

3. **Verify**:

   * Run `uv-lens check` (simulated via `python -m uv_lens.cli check`) to verify the progress bar appears when cache is missing or refresh is forced.

   * Verify `uv-lens check --format json` still outputs valid JSON to stdout (progress bar should be on stderr).

