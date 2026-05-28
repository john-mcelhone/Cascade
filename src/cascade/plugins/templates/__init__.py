"""User-facing plugin templates.

These files are intentionally importable so the test suite can verify
the template still loads cleanly after refactors, but the recommended
distribution channel is to COPY the file body into a fresh location
(via the CLI's `cascade plugin template > my_loss.py` command or via
the web UI's "Download template" button) so the user owns the file
outright.
"""
