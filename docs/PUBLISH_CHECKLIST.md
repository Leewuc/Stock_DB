# Publish Checklist

Before pushing this project to GitHub:

1. Confirm `.env` is not staged.
2. Confirm `signals.db` is not staged.
3. Replace any real tokens or chat IDs with placeholders in shared examples.
4. Verify `README.md` matches the current runtime behavior.
5. Decide whether `infer.py` should remain as legacy code or move to an archive folder later.
6. Create the repository and commit only public-safe files.

Recommended first commit set:

- `README.md`
- `.gitignore`
- `.env.example`
- `requirements.txt`
- `st_pred.py`
- `infer.py`
- `docs/PUBLISH_CHECKLIST.md`
