# Solution Steps

1. Extend the database with immutable `prompt_versions`, prompt activation history, current prompt identities, and per-dimension judge scores. Keep migrations additive so an existing Docker volume from the starter project is repaired rather than requiring deletion.

2. Generate each prompt identity from the assistant, variant, and exact full prompt text. Archive a version before changing the current prompt binding, and resolve historical identities directly from the immutable version table.

3. Implement prompt restoration by looking up the historical identity, verifying that it belongs to the requested assistant, rebinding its original variant, and checking that both the restored identity and exact text match.

4. Implement shared wording updates by retaining each prompt’s assistant-specific instruction body while replacing the common leading clause for every assistant and variant. Store each resulting full prompt as a new immutable version.

5. Persist the selected prompt identity on every assistant output so an output always remains traceable to the exact system prompt that generated it.

6. Replace the single overall judge score with independent factuality, coverage, and usability scores plus textual observations. Validate all returned JSON and score ranges, retain the complete raw judge response, and collect multiple samples per output to expose variation.

7. Aggregate observations separately for every dimension, reporting mean, population spread, minimum, maximum, count, and individual raw observations.

8. Compare each candidate dimension against its approved baseline independently. Use the approved score spread, with a small fixed floor, as the declared meaningful-drop allowance and reject the release if any dimension falls below its threshold, regardless of the combined score.

9. Keep release decision logic pure and based only on dimension summaries and approved baseline data, ensuring equivalent observations produce the same decision even if run IDs or observation ordering differ.

10. Update readiness and `run.sh` to apply migrations, verify prompt identity resolution, run tests, ping the real provider when an API key is configured, and execute the seeded proposed-release evaluation. Configure `OPENAI_API_KEY` in `.env` before running `./run.sh`.

